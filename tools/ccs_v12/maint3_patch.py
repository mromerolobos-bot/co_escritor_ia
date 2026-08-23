from __future__ import annotations

import sys
from pathlib import Path


def write(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    print(f"WROTE {path}")


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{label}: expected exactly 1 match, found {count}")
    return text.replace(old, new, 1)


def patch(root: Path) -> None:
    app = root / "app"
    core = app / "v12_core"
    if not (app / "main.py").is_file():
        raise RuntimeError(f"Not a CCS working copy: {root}")

    intent_py = '''from __future__ import annotations

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
    clothing_change_intensity: str = "none"
    pose_change_intensity: str = "none"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def model_dump(self) -> dict[str, Any]:
        return asdict(self)

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def parse_generation_intent(request: Any, character_profile: Any = None) -> GenerationIntent:
    prompt = (getattr(request, "prompt", "") or "").lower()
    has_profile = bool(getattr(request, "character_id", None) or character_profile)
    has_character_reference = bool(getattr(request, "character_image", None))
    pose_reference = bool(getattr(request, "pose_image", None))
    background = bool(getattr(request, "background_image", None))
    objects = bool(getattr(request, "object_image", None))
    style = bool(getattr(request, "style_image", None))
    identity = has_profile or has_character_reference

    clothing_terms = (
        "ropa", "vestido", "outfit", "clothes", "clothing", "shirt", "dress",
        "jacket", "bikini", "uniform", "traje", "camisa", "pantalon", "pantalón",
        "falda", "shorts", "top", "bra", "sujetador", "sostén", "underwear",
    )
    clothing = _contains_any(prompt, clothing_terms)

    radical_clothing_terms = (
        "desnuda", "desnudo", "nude", "naked", "fully nude", "topless", "bare breasts",
        "bare chest", "sin ropa", "without clothes", "remove all clothing", "remove every garment",
        "quitar toda la ropa", "quita toda la ropa", "sin vestido", "remove dress", "remove the dress",
        "replace entire outfit", "cambiar todo el atuendo", "cambia todo el atuendo",
    )
    mild_clothing_terms = (
        "cambiar ropa", "cambia la ropa", "change clothes", "change outfit", "cambiar vestido",
        "change dress", "cambiar color", "change color", "color del vestido", "material", "fabric",
        "estilo de ropa", "clothing style",
    )
    if _contains_any(prompt, radical_clothing_terms):
        clothing_change_intensity = "radical"
        clothing = True
    elif clothing and (_contains_any(prompt, mild_clothing_terms) or clothing):
        clothing_change_intensity = "mild"
    else:
        clothing_change_intensity = "none"

    strong_pose_terms = (
        "una pierna levantada", "pierna levantada", "levanta una pierna", "leg raised", "one leg raised",
        "lifted leg", "arms overhead", "brazos arriba", "brazos sobre la cabeza", "sentada", "sentado",
        "sitting", "lying", "acostada", "acostado", "kneeling", "arrodillada", "arrodillado",
        "squatting", "en cuclillas", "jumping", "saltando", "running", "corriendo", "dancing", "bailando",
        "high kick", "patada alta",
    )
    moderate_pose_terms = (
        "walking", "caminando", "turn around", "girando", "de perfil", "profile pose", "pose",
    )
    if pose_reference or _contains_any(prompt, strong_pose_terms):
        pose_change_intensity = "strong"
    elif _contains_any(prompt, moderate_pose_terms):
        pose_change_intensity = "moderate"
    else:
        pose_change_intensity = "none"

    pose = pose_reference or pose_change_intensity != "none"
    targeted_terms = (
        "cambia", "cambiar", "reemplaza", "replace", "edit", "editar", "mantener",
        "keep", "solo", "only", "misma", "mismo", "same", "quita", "quitar", "remove",
    )
    has_edit_reference = any((pose_reference, background, objects, style, has_character_reference))
    explicit_edit = any(t in prompt for t in targeted_terms) or clothing_change_intensity != "none" or pose_change_intensity != "none"
    operation = "targeted_edit" if explicit_edit and (has_edit_reference or identity or clothing or pose) else "generate"
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
        clothing_change_intensity=clothing_change_intensity,
        pose_change_intensity=pose_change_intensity,
    )
'''
    write(core / "intent.py", intent_py)

    router_py = '''from __future__ import annotations

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
    clothing_change_intensity: str = "none"
    pose_change_intensity: str = "none"
    localized_clothing_mask: bool = False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["reasons"] = list(self.reasons)
        data["controls"] = list(self.controls)
        data["effective_denoise"] = self.denoise
        return data

    def model_dump(self) -> dict[str, Any]:
        return self.to_dict()

    def dict(self) -> dict[str, Any]:
        return self.to_dict()


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _set_effective_denoise(request: Any, value: float) -> None:
    if request is None:
        return
    # GenerateRequest is mutable in the current Pydantic configuration. Mutating the same
    # request object guarantees that downstream legacy workflow code receives the router's
    # effective denoise instead of silently falling back to the original 0.58 value.
    try:
        request.denoise = value
    except Exception:
        pass


def route_pipeline(
    request_or_intent: Any,
    intent: GenerationIntent | None = None,
    manual_mode: str | None = None,
) -> PipelinePlan:
    if isinstance(request_or_intent, GenerationIntent):
        actual_intent = request_or_intent
        actual_request = None
        mode = (manual_mode or "auto").lower()
        requested_denoise = 0.58
        lock_val = True
        has_pose_reference = False
    else:
        actual_request = request_or_intent
        actual_intent = intent or GenerationIntent("generate", False, False, False, False, False, False, "portrait", False, False)
        mode = (manual_mode or getattr(actual_request, "mode", "auto") or "auto").lower()
        requested_denoise = float(getattr(actual_request, "denoise", 0.58))
        lock_val = bool(getattr(actual_request, "identity_lock", True))
        has_pose_reference = bool(getattr(actual_request, "pose_image", None))

    controls = tuple(name for name, enabled in (
        ("identity", actual_intent.identity),
        ("pose", actual_intent.pose),
        ("clothing", actual_intent.clothing),
        ("background", actual_intent.background),
        ("objects", actual_intent.objects),
        ("style", actual_intent.style),
    ) if enabled)

    common = {
        "clothing_change_intensity": actual_intent.clothing_change_intensity,
        "pose_change_intensity": actual_intent.pose_change_intensity,
    }

    # Manual modes remain manual. Legacy clothes is never selected automatically.
    if mode != "auto":
        effective = requested_denoise
        if mode == "edit":
            if actual_intent.clothing_change_intensity == "radical" and actual_intent.pose_change_intensity == "strong":
                effective = _clamp(max(requested_denoise, 0.92), 0.90, 0.95)
            elif actual_intent.clothing_change_intensity == "radical":
                effective = _clamp(max(requested_denoise, 0.88), 0.85, 0.92)
        _set_effective_denoise(actual_request, effective)
        return PipelinePlan(
            pipeline=mode,
            reasons=(f"manual mode override: {mode}",),
            controls=controls,
            denoise=effective,
            identity_strategy="locked" if actual_intent.identity and lock_val else "standard",
            manual_override=True,
            localized_clothing_mask=(mode == "clothes"),
            **common,
        )

    clothing_intensity = actual_intent.clothing_change_intensity
    pose_intensity = actual_intent.pose_change_intensity

    if clothing_intensity == "radical" and pose_intensity == "strong":
        effective = _clamp(max(requested_denoise, 0.92), 0.90, 0.95)
        pipeline = "sdxl_pose" if has_pose_reference else ("sdxl_identity" if actual_intent.identity else "kontext")
        reasons = ("radical clothing/body edit", "strong pose change", "full-frame reconstruction; localized clothes mask disabled")
    elif clothing_intensity == "radical":
        effective = _clamp(max(requested_denoise, 0.88), 0.85, 0.92)
        pipeline = "sdxl_identity" if actual_intent.identity else "kontext"
        reasons = ("radical clothing/body edit", "full-frame reconstruction; localized clothes mask disabled")
    elif has_pose_reference:
        effective = requested_denoise
        pipeline = "sdxl_pose"
        reasons = ("pose reference present",)
    elif actual_intent.operation == "targeted_edit" and (actual_intent.background or actual_intent.objects or actual_intent.style):
        effective = min(requested_denoise, 0.58)
        pipeline = "kontext"
        reasons = ("targeted edit with scene/object/style reference",)
    elif clothing_intensity == "mild":
        effective = _clamp(requested_denoise if requested_denoise > 0.58 else 0.60, 0.58, 0.65)
        pipeline = "sdxl_identity" if actual_intent.identity else "kontext"
        reasons = ("mild clothing edit", "full-frame edit; localized clothes mask disabled")
    elif actual_intent.pose:
        effective = _clamp(max(requested_denoise, 0.68 if pose_intensity == "strong" else requested_denoise), 0.3, 0.82)
        pipeline = "sdxl_identity" if actual_intent.identity else "sdxl_text"
        reasons = ("text-guided pose change",)
    elif actual_intent.identity:
        effective = requested_denoise
        pipeline = "sdxl_identity"
        reasons = ("character profile or canonical identity active",)
    else:
        effective = requested_denoise
        pipeline = "sdxl_text"
        reasons = ("plain text/new-scene generation",)

    _set_effective_denoise(actual_request, effective)
    return PipelinePlan(
        pipeline=pipeline,
        reasons=reasons,
        controls=controls,
        denoise=effective,
        identity_strategy="locked" if actual_intent.identity and lock_val else ("standard" if actual_intent.identity else "none"),
        manual_override=False,
        localized_clothing_mask=False,
        **common,
    )
'''
    write(core / "router.py", router_py)

    actions_path = core / "actions.py"
    actions = actions_path.read_text(encoding="utf-8")
    actions = actions.replace('description="Edición completa de vestuario sin segmentación destructiva.",', 'description="Edición full-frame de vestuario; la intensidad se ajusta automáticamente según el cambio pedido.",')
    actions = actions.replace('description="Segmentación localizada de prendas manteniendo el cuerpo y entorno.",', 'description="Edición full-frame de vestuario; la intensidad se ajusta automáticamente según el cambio pedido.",')
    actions = actions.replace('default_mode="clothes",', 'default_mode="edit",')
    actions = actions.replace('recommended_denoise=0.88', 'recommended_denoise=0.60')
    write(actions_path, actions)

    main_path = app / "main.py"
    main = main_path.read_text(encoding="utf-8")
    marker = '    nudity_required = any(term in text for term in ("topless", "bare breasts", "desnuda", "desnudo", "fully nude", "naked"))\n'
    strong_pose_block = '''    strong_pose_terms = (\n        "una pierna levantada", "pierna levantada", "levanta una pierna", "leg raised", "one leg raised",\n        "lifted leg", "arms overhead", "brazos arriba", "sentada", "sentado", "sitting", "lying",\n        "kneeling", "arrodillada", "arrodillado", "squatting", "en cuclillas", "jumping", "saltando",\n        "running", "corriendo", "dancing", "bailando", "high kick", "patada alta",\n    )\n    if any(term in text for term in strong_pose_terms):\n        physical_relations.append(\n            "Honor the requested strong pose exactly while keeping one coherent adult body: exactly two arms and two legs, "\n            "no duplicated or ghost limbs. If one leg is requested raised, show exactly one visible leg raised in the requested action "\n            "while the other leg provides plausible support or balance; preserve coherent hips, knees, shoulders, elbows, hands and feet."\n        )\n    nudity_required = any(term in text for term in ("topless", "bare breasts", "desnuda", "desnudo", "fully nude", "naked"))\n'''
    if strong_pose_block not in main:
        main = replace_once(main, marker, strong_pose_block, "main strong-pose contract")

    # MAINT-0002 must remain: automatic nudity/clothing requests resolve to edit, never clothes.
    forbidden = '    elif mask_text and nudity_required:\n        resolved_mode = "clothes"\n'
    if forbidden in main:
        main = main.replace(forbidden, '    elif mask_text and nudity_required:\n        resolved_mode = "edit"\n', 1)

    write(main_path, main)

    test_py = '''from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from v12_core.actions import ACTION_PRESETS
from v12_core.intent import parse_generation_intent
from v12_core.router import route_pipeline


def req(prompt: str, **kwargs):
    data = dict(
        prompt=prompt,
        character_id="char-test",
        character_image=None,
        pose_image=None,
        background_image=None,
        object_image=None,
        style_image=None,
        aspect="portrait",
        mode="auto",
        denoise=0.58,
        identity_lock=True,
    )
    data.update(kwargs)
    return SimpleNamespace(**data)


class Maint3Tests(unittest.TestCase):
    def test_mild_clothing_edit_full_frame(self):
        r = req("cambia el color del vestido a rojo")
        i = parse_generation_intent(r)
        p = route_pipeline(r, i)
        self.assertEqual(i.clothing_change_intensity, "mild")
        self.assertNotIn(p.pipeline, {"clothes", "sdxl_clothes"})
        self.assertLessEqual(p.denoise, 0.65)
        self.assertFalse(p.localized_clothing_mask)

    def test_radical_clothing_edit_raises_denoise(self):
        r = req("quita toda la ropa del personaje")
        i = parse_generation_intent(r)
        p = route_pipeline(r, i)
        self.assertEqual(i.clothing_change_intensity, "radical")
        self.assertGreaterEqual(p.denoise, 0.85)
        self.assertNotIn(p.pipeline, {"clothes", "sdxl_clothes"})
        self.assertFalse(p.localized_clothing_mask)
        self.assertAlmostEqual(r.denoise, p.denoise)

    def test_radical_plus_leg_raised_is_strong(self):
        r = req("quita el vestido, tomando cerveza y con una pierna levantada")
        i = parse_generation_intent(r)
        p = route_pipeline(r, i)
        self.assertEqual(i.clothing_change_intensity, "radical")
        self.assertEqual(i.pose_change_intensity, "strong")
        self.assertGreaterEqual(p.denoise, 0.90)
        self.assertFalse(p.localized_clothing_mask)

    def test_pose_reference_prefers_pose_pipeline_for_radical(self):
        r = req("remove the dress", pose_image="pose.png")
        i = parse_generation_intent(r)
        p = route_pipeline(r, i)
        self.assertEqual(i.pose_change_intensity, "strong")
        self.assertEqual(p.pipeline, "sdxl_pose")
        self.assertGreaterEqual(p.denoise, 0.90)

    def test_manual_clothes_remains_explicit_legacy(self):
        r = req("change clothes", mode="clothes", denoise=0.88)
        i = parse_generation_intent(r)
        p = route_pipeline(r, i)
        self.assertTrue(p.manual_override)
        self.assertEqual(p.pipeline, "clothes")
        self.assertTrue(p.localized_clothing_mask)

    def test_change_clothes_preset_does_not_force_legacy_mask(self):
        preset = ACTION_PRESETS["change_clothes"]
        self.assertEqual(preset.default_mode, "edit")
        self.assertLessEqual(preset.recommended_denoise, 0.65)

    def test_pipeline_metadata_is_auditable(self):
        r = req("quita el vestido y levanta una pierna")
        i = parse_generation_intent(r)
        p = route_pipeline(r, i)
        data = p.to_dict()
        self.assertEqual(data["clothing_change_intensity"], "radical")
        self.assertEqual(data["pose_change_intensity"], "strong")
        self.assertEqual(data["effective_denoise"], p.denoise)
        self.assertFalse(data["localized_clothing_mask"])


if __name__ == "__main__":
    unittest.main()
'''
    write(app / "test_v12_maint3.py", test_py)

    print("MAINT3_PATCH_APPLIED")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: maint3_patch.py <CCS_ROOT>", file=sys.stderr)
        return 2
    patch(Path(sys.argv[1]).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
