from __future__ import annotations

from pathlib import Path
import json
import re
import textwrap

ROOT = Path.cwd()
APP = ROOT / "app"
CORE = APP / "v12_core"
PROGRESS = ROOT / "_v12_progress"
MAIN = APP / "main.py"

if not MAIN.exists() or not CORE.exists():
    raise SystemExit("PHASE2_ERROR: expected working-copy app/main.py and app/v12_core")

CORE.mkdir(parents=True, exist_ok=True)
PROGRESS.mkdir(parents=True, exist_ok=True)

intent_py = r'''from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class GenerationIntent:
    operation: str
    identity: bool
    pose: bool
    clothing: bool
    background: bool
    objects: bool
    style: bool
    framing: str
    has_character_profile: bool
    has_character_reference: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def parse_generation_intent(request: Any) -> GenerationIntent:
    prompt = (getattr(request, "prompt", "") or "").lower()
    has_profile = bool(getattr(request, "character_id", None))
    has_character_reference = bool(getattr(request, "character_image", None))
    pose = bool(getattr(request, "pose_image", None))
    background = bool(getattr(request, "background_image", None))
    objects = bool(getattr(request, "object_image", None))
    style = bool(getattr(request, "style_image", None))
    identity = has_profile or has_character_reference
    clothing_terms = (
        "ropa", "vestido", "outfit", "clothes", "clothing", "shirt", "dress",
        "jacket", "bikini", "uniform", "traje", "camisa", "pantalon", "pantalón",
    )
    clothing = any(term in prompt for term in clothing_terms)
    targeted_terms = (
        "cambia", "cambiar", "reemplaza", "replace", "edit", "editar", "mantener",
        "keep", "solo", "only", "misma", "mismo", "same",
    )
    has_edit_reference = any((pose, background, objects, style, has_character_reference))
    operation = "targeted_edit" if has_edit_reference and any(t in prompt for t in targeted_terms) else "generate"
    framing = getattr(request, "aspect", "portrait") or "portrait"
    return GenerationIntent(
        operation=operation,
        identity=identity,
        pose=pose,
        clothing=clothing,
        background=background,
        objects=objects,
        style=style,
        framing=framing,
        has_character_profile=has_profile,
        has_character_reference=has_character_reference,
    )
'''

router_py = r'''from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from .intent import GenerationIntent


@dataclass(frozen=True)
class PipelinePlan:
    pipeline: str
    reasons: tuple[str, ...]
    controls: tuple[str, ...]
    denoise: float
    identity_strategy: str
    manual_override: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        data["controls"] = list(self.controls)
        return data


def route_pipeline(request: Any, intent: GenerationIntent) -> PipelinePlan:
    mode = (getattr(request, "mode", "auto") or "auto").lower()
    controls = tuple(name for name, enabled in (
        ("identity", intent.identity),
        ("pose", intent.pose),
        ("clothing", intent.clothing),
        ("background", intent.background),
        ("objects", intent.objects),
        ("style", intent.style),
    ) if enabled)

    if mode != "auto":
        return PipelinePlan(
            pipeline=mode,
            reasons=(f"manual mode override: {mode}",),
            controls=controls,
            denoise=float(getattr(request, "denoise", 0.58)),
            identity_strategy="locked" if intent.identity and getattr(request, "identity_lock", True) else "standard",
            manual_override=True,
        )

    if intent.operation == "targeted_edit" and (intent.background or intent.objects or intent.style):
        return PipelinePlan(
            pipeline="kontext",
            reasons=("targeted edit with scene/object/style reference",),
            controls=controls,
            denoise=min(float(getattr(request, "denoise", 0.58)), 0.58),
            identity_strategy="locked" if intent.identity else "standard",
        )
    if intent.pose:
        return PipelinePlan(
            pipeline="sdxl_pose",
            reasons=("pose reference present",),
            controls=controls,
            denoise=float(getattr(request, "denoise", 0.58)),
            identity_strategy="faceid_or_profile" if intent.identity else "standard",
        )
    if intent.identity:
        return PipelinePlan(
            pipeline="sdxl_identity",
            reasons=("character profile or character reference present",),
            controls=controls,
            denoise=float(getattr(request, "denoise", 0.58)),
            identity_strategy="locked" if getattr(request, "identity_lock", True) else "faceid_or_profile",
        )
    return PipelinePlan(
        pipeline="sdxl_text",
        reasons=("plain text/new-scene generation",),
        controls=controls,
        denoise=float(getattr(request, "denoise", 0.58)),
        identity_strategy="none",
    )
'''

evaluation_py = r'''from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class EvaluationResult:
    identity: float | None = None
    pose: float | None = None
    clothing: float | None = None
    style: float | None = None
    scene: float | None = None
    objects: float | None = None
    anatomy: float | None = None
    overall: float | None = None
    issues: list[str] = field(default_factory=list)

    def recompute_overall(self) -> float | None:
        values = [
            self.identity, self.pose, self.clothing, self.style,
            self.scene, self.objects, self.anatomy,
        ]
        known = [float(v) for v in values if v is not None]
        self.overall = sum(known) / len(known) if known else None
        return self.overall

    def to_dict(self) -> dict[str, Any]:
        self.recompute_overall()
        return asdict(self)


@dataclass(frozen=True)
class QualityPolicy:
    minimum_identity: float = 0.72
    minimum_overall: float = 0.72
    max_retries: int = 2


@dataclass(frozen=True)
class RetryDecision:
    should_retry: bool
    reason: str


def decide_retry(evaluation: EvaluationResult, policy: QualityPolicy, attempt: int) -> RetryDecision:
    if attempt >= policy.max_retries:
        return RetryDecision(False, "retry budget exhausted")
    evaluation.recompute_overall()
    if evaluation.identity is not None and evaluation.identity < policy.minimum_identity:
        return RetryDecision(True, "identity below threshold")
    if evaluation.overall is not None and evaluation.overall < policy.minimum_overall:
        return RetryDecision(True, "overall evaluated quality below threshold")
    return RetryDecision(False, "no evaluated dimension requires retry")
'''

test_py = r'''from __future__ import annotations

import unittest
from types import SimpleNamespace

from v12_core.evaluation import EvaluationResult, QualityPolicy, decide_retry
from v12_core.intent import parse_generation_intent
from v12_core.router import route_pipeline


def req(**kwargs):
    defaults = dict(
        prompt="portrait in a city", character_id=None, character_image=None,
        object_image=None, background_image=None, pose_image=None, style_image=None,
        aspect="portrait", mode="auto", denoise=0.58, identity_lock=True,
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


class Phase2Tests(unittest.TestCase):
    def test_plain_text(self):
        r = req()
        i = parse_generation_intent(r)
        p = route_pipeline(r, i)
        self.assertEqual(p.pipeline, "sdxl_text")

    def test_identity_profile(self):
        r = req(character_id="joel")
        i = parse_generation_intent(r)
        self.assertTrue(i.identity)
        self.assertEqual(route_pipeline(r, i).pipeline, "sdxl_identity")

    def test_pose(self):
        r = req(pose_image="pose.png")
        i = parse_generation_intent(r)
        self.assertTrue(i.pose)
        self.assertEqual(route_pipeline(r, i).pipeline, "sdxl_pose")

    def test_targeted_reference_edit(self):
        r = req(prompt="cambia solo el fondo", background_image="bg.png")
        i = parse_generation_intent(r)
        self.assertEqual(i.operation, "targeted_edit")
        self.assertEqual(route_pipeline(r, i).pipeline, "kontext")

    def test_manual_override(self):
        r = req(mode="kontext")
        p = route_pipeline(r, parse_generation_intent(r))
        self.assertTrue(p.manual_override)
        self.assertEqual(p.pipeline, "kontext")

    def test_evaluation_never_fabricates(self):
        e = EvaluationResult(identity=0.8)
        data = e.to_dict()
        self.assertIsNone(data["pose"])
        self.assertIsNone(data["anatomy"])
        self.assertAlmostEqual(data["overall"], 0.8)

    def test_retry_missing_dimensions(self):
        e = EvaluationResult()
        d = decide_retry(e, QualityPolicy(), attempt=0)
        self.assertFalse(d.should_retry)

    def test_retry_low_identity(self):
        e = EvaluationResult(identity=0.5)
        d = decide_retry(e, QualityPolicy(minimum_identity=0.7), attempt=0)
        self.assertTrue(d.should_retry)


if __name__ == "__main__":
    unittest.main()
'''

(CORE / "intent.py").write_text(intent_py, encoding="utf-8")
(CORE / "router.py").write_text(router_py, encoding="utf-8")
(CORE / "evaluation.py").write_text(evaluation_py, encoding="utf-8")
(APP / "test_v12_phase2.py").write_text(test_py, encoding="utf-8")

main = MAIN.read_text(encoding="utf-8")
import_line = "from v12_core.intent import parse_generation_intent\nfrom v12_core.router import route_pipeline\nfrom v12_core.evaluation import EvaluationResult\n"
if "from v12_core.intent import parse_generation_intent" not in main:
    anchor = "from identity import build_profile, list_profiles, load_profile, score_identity\n"
    if anchor not in main:
        raise SystemExit("PHASE2_ERROR: import anchor not found")
    main = main.replace(anchor, anchor + import_line, 1)

# Add metadata to every newly-created job at the API boundary, without changing existing workflow selection yet.
if "pipeline_plan_v12" not in main:
    pattern = re.compile(r'(def generate\([^\n]*\):\n)([ \t]+)')
    match = pattern.search(main)
    if not match:
        raise SystemExit("PHASE2_ERROR: generate() anchor not found")
    indent = match.group(2)
    block = (
        f"{indent}intent_v12 = parse_generation_intent(request)\n"
        f"{indent}pipeline_plan_v12 = route_pipeline(request, intent_v12)\n"
    )
    main = main[:match.end()] + block + main[match.end():]

    # After a create_job(...) assignment, attach metadata through update_job so existing create_job signature stays compatible.
    gen_start = main.find("def generate(")
    gen_end = main.find("\ndef ", gen_start + 1)
    if gen_end < 0:
        gen_end = len(main)
    region = main[gen_start:gen_end]
    m = re.search(r'([ \t]*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*create_job\(([^\n]*)\)\n', region)
    if not m:
        raise SystemExit("PHASE2_ERROR: create_job assignment inside generate() not found")
    job_var = m.group(2)
    insert_at = gen_start + m.end()
    metadata_block = (
        f"{m.group(1)}update_job({job_var}[\"job_id\"], intent_v12=intent_v12.to_dict(), "
        f"pipeline_plan_v12=pipeline_plan_v12.to_dict(), evaluation_v12=EvaluationResult().to_dict())\n"
    )
    main = main[:insert_at] + metadata_block + main[insert_at:]

MAIN.write_text(main, encoding="utf-8")

(PROGRESS / "PHASE2_ROUTER_EVAL.md").write_text(textwrap.dedent('''\
# V1.2 Phase 2 — Intent, Router and Evaluation Core

Implemented additively on the working copy.

## Routing matrix
- plain text/new scene -> `sdxl_text`
- character profile/reference -> `sdxl_identity`
- pose reference -> `sdxl_pose`
- targeted edit with background/object/style reference -> `kontext`
- explicit non-auto mode -> manual override

Phase 2 deliberately does not replace the existing workflow builders. It stores intent/router/evaluation metadata at the job boundary, preserving current generation behavior while making routing decisions observable and testable.

Evaluation dimensions that are not actually measured remain `None`; no synthetic quality scores are generated. Retry primitives are bounded and deterministic but do not trigger additional renders yet.
'''), encoding="utf-8")

print("PHASE2_APPLIED")
print("CHANGED app/v12_core/intent.py")
print("CHANGED app/v12_core/router.py")
print("CHANGED app/v12_core/evaluation.py")
print("CHANGED app/test_v12_phase2.py")
print("CHANGED app/main.py")
print("CHANGED _v12_progress/PHASE2_ROUTER_EVAL.md")
