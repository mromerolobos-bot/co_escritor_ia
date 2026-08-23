from __future__ import annotations

import re
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


def patch_main(main_path: Path) -> None:
    main = main_path.read_text(encoding="utf-8")

    import_line = "from v12_core.intent_contract import extract_text_contract\n"
    if import_line not in main:
        marker = "class ConnectRequest(BaseModel):"
        if marker not in main:
            raise RuntimeError("main.py import insertion marker missing")
        main = main.replace(marker, import_line + "\n" + marker, 1)

    old = "    physical_relations: list[str] = []\n"
    new = (
        "    text_contract = extract_text_contract(user_prompt, translated_prompt)\n"
        "    physical_relations: list[str] = list(text_contract.prompt_constraints)\n"
    )
    if new not in main:
        main = replace_once(main, old, new, "intent-contract initialization")

    # Replace the AUTO mode decision block with structural-rebuild-aware routing.
    pattern = re.compile(
        r"    new_scene_terms = \(.*?\n    mask_expand = 56 if nudity_required and mask_scope in \{\"upper_garment\", \"full_garment\"\} else 24\n",
        re.S,
    )
    replacement = '''    new_scene_terms = (\n        "manejando", "conduciendo", "driving", "jugando", "playing", "en la playa", "on the beach",\n        "en un auto", "in a car", "escena nueva", "new scene",\n    )\n    structural_rebuild = bool(text_contract.requires_structural_rebuild)\n    if requested_mode != "auto":\n        resolved_mode = requested_mode\n    elif has_pose:\n        resolved_mode = "pose"\n    elif structural_rebuild:\n        # Strong action/pose requests must not stay anchored to the original body layout.\n        # Generate a fresh scene scaffold first, then let the existing identity-refine pass\n        # restore the registered/canonical character. This is intentionally full-frame and\n        # does not use the legacy localized clothing mask.\n        resolved_mode = "new"\n    elif compound_edit:\n        resolved_mode = "compound"\n    elif mask_text and nudity_required:\n        # MAINT-0002 invariant: automatic clothing/body edits never use localized clothes mask.\n        resolved_mode = "edit"\n    elif mask_text:\n        resolved_mode = "edit"\n    elif any(term in text for term in new_scene_terms):\n        resolved_mode = "new"\n    else:\n        resolved_mode = "edit"\n    mask_expand = 56 if nudity_required and mask_scope in {"upper_garment", "full_garment"} else 24\n'''
    main, n = pattern.subn(replacement, main, count=1)
    if n != 1:
        raise RuntimeError(f"main routing block replacement failed: {n}")

    # Make the text contract auditable from the existing prompt contract metadata.
    old_tail = '        "compound_edit": compound_edit,\n    }\n'
    new_tail = (
        '        "compound_edit": compound_edit,\n'
        '        "intent_contract": text_contract.to_dict(),\n'
        '        "requires_structural_rebuild": structural_rebuild,\n'
        '    }\n'
    )
    if new_tail not in main:
        main = replace_once(main, old_tail, new_tail, "prompt-contract metadata")

    # Preserve the no-auto-mask invariant even if an older source copy is encountered.
    main = main.replace(
        '    elif mask_text and nudity_required:\n        resolved_mode = "clothes"\n',
        '    elif mask_text and nudity_required:\n        resolved_mode = "edit"\n',
    )

    write(main_path, main)


def patch(root: Path) -> None:
    app = root / "app"
    core = app / "v12_core"
    if not (app / "main.py").is_file():
        raise RuntimeError(f"Not a Cinematic Character Studio working copy: {root}")

    intent_contract = r'''from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass
from typing import Any


COUNT_WORDS = {
    "one": 1, "un": 1, "una": 1, "1": 1,
    "two": 2, "dos": 2, "2": 2,
    "three": 3, "tres": 3, "3": 3,
}


def _fold(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", text.lower()).strip()


@dataclass(frozen=True)
class RequiredObject:
    name: str
    count: int
    relation: str = "present"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TextIntentContract:
    actions: tuple[str, ...]
    objects: tuple[RequiredObject, ...]
    pose_constraints: tuple[str, ...]
    prompt_constraints: tuple[str, ...]
    forbidden_additions: tuple[str, ...]
    change_magnitude: str
    requires_structural_rebuild: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "actions": list(self.actions),
            "objects": [obj.to_dict() for obj in self.objects],
            "pose_constraints": list(self.pose_constraints),
            "prompt_constraints": list(self.prompt_constraints),
            "forbidden_additions": list(self.forbidden_additions),
            "change_magnitude": self.change_magnitude,
            "requires_structural_rebuild": self.requires_structural_rebuild,
        }


def _explicit_count_objects(text: str) -> list[RequiredObject]:
    out: list[RequiredObject] = []
    # Generic explicit count extraction. Keep the noun phrase intentionally short so it can
    # become a strict generation constraint without pretending to be a full NLP parser.
    rx = re.compile(r"\b(one|two|three|un|una|dos|tres|1|2|3)\s+([a-z0-9_-]+(?:\s+[a-z0-9_-]+)?)")
    for count_word, noun in rx.findall(text):
        count = COUNT_WORDS[count_word]
        noun = noun.strip()
        if noun in {"leg", "legs", "pierna", "piernas", "arm", "arms", "brazo", "brazos"}:
            continue
        out.append(RequiredObject(noun, count))
    return out


def extract_text_contract(user_prompt: str, translated_prompt: str = "") -> TextIntentContract:
    text = _fold(f"{user_prompt} {translated_prompt}")
    actions: list[str] = []
    objects = _explicit_count_objects(text)
    pose: list[str] = []
    constraints: list[str] = []

    # Global invariants: preserve user intent, prevent accidental duplication and prevent the
    # application from injecting bars, coverings or replacement clothing that was not asked for.
    constraints.append(
        "Follow every explicit user instruction. Preserve attributes the user did not ask to change, but do not preserve the original pose, garment, object layout or scene structure when that would conflict with an explicit requested change."
    )
    constraints.append(
        "Keep one coherent adult main subject unless the user explicitly requests multiple people. Keep exactly two arms and two legs, with coherent shoulders, elbows, wrists, hips, knees, ankles, hands and feet; no duplicated or ghost limbs."
    )
    constraints.append(
        "Do not add censor bars, opaque patches, strategic coverings, modesty layers, replacement garments or other unrequested coverage."
    )

    forbidden = (
        "censor bars",
        "opaque censorship patches",
        "unrequested covering",
        "unrequested extra limbs",
        "unrequested duplicate objects",
    )

    strong_pose_terms = {
        "one leg raised": "Show exactly one leg raised while the other leg provides plausible support or balance.",
        "leg raised": "Show exactly one leg raised while the other leg provides plausible support or balance.",
        "una pierna levantada": "Show exactly one leg raised while the other leg provides plausible support or balance.",
        "pierna levantada": "Show exactly one leg raised while the other leg provides plausible support or balance.",
        "arms overhead": "Place both arms overhead with coherent shoulders, elbows, wrists and hands.",
        "brazos arriba": "Place both arms overhead with coherent shoulders, elbows, wrists and hands.",
        "sitting": "Show a clearly seated pose with anatomically plausible hip, knee and foot placement.",
        "sentada": "Show a clearly seated pose with anatomically plausible hip, knee and foot placement.",
        "sentado": "Show a clearly seated pose with anatomically plausible hip, knee and foot placement.",
        "kneeling": "Show a clearly kneeling pose with anatomically plausible knee and foot placement.",
        "arrodillada": "Show a clearly kneeling pose with anatomically plausible knee and foot placement.",
        "squatting": "Show a coherent squat with balanced hips, knees and feet.",
        "en cuclillas": "Show a coherent squat with balanced hips, knees and feet.",
        "high kick": "Show one coherent high kick with exactly one kicking leg and one supporting leg.",
        "patada alta": "Show one coherent high kick with exactly one kicking leg and one supporting leg.",
        "jumping": "Show a coherent airborne jumping pose without duplicated limbs.",
        "saltando": "Show a coherent airborne jumping pose without duplicated limbs.",
        "dancing": "Show a clear dynamic dance pose without duplicated limbs.",
        "bailando": "Show a clear dynamic dance pose without duplicated limbs.",
    }
    for term, directive in strong_pose_terms.items():
        if term in text and directive not in pose:
            pose.append(directive)

    strong_actions = (
        ("drinking", "drinking"), ("tomando", "drinking"), ("beber", "drinking"),
        ("holding", "holding"), ("sosteniendo", "holding"), ("carrying", "carrying"),
        ("driving", "driving"), ("conduciendo", "driving"), ("manejando", "driving"),
        ("running", "running"), ("corriendo", "running"),
        ("dancing", "dancing"), ("bailando", "dancing"),
        ("jumping", "jumping"), ("saltando", "jumping"),
    )
    for term, name in strong_actions:
        if term in text and name not in actions:
            actions.append(name)

    # Common interaction mapping: when the user says "drinking beer" without a number, the
    # natural requested count is one drink. Explicit numeric counts always win.
    has_explicit_beer_count = any("beer" in obj.name or "cerveza" in obj.name for obj in objects)
    if ("beer" in text or "cerveza" in text) and "drinking" in actions and not has_explicit_beer_count:
        objects.append(RequiredObject("beer drink", 1, "held-and-drunk"))

    if "driving" in actions:
        constraints.append(
            "For driving, show exactly one steering wheel and a coherent driver pose; if both hands are requested on the wheel, show exactly two hands contacting that one wheel."
        )

    for obj in objects:
        constraints.append(
            f"Show exactly {obj.count} instance(s) of {obj.name}; do not add duplicate or extra instances."
        )

    constraints.extend(pose)

    radical_change_terms = (
        "replace entire outfit", "change entire outfit", "cambiar todo el atuendo", "cambia todo el atuendo",
        "remove all clothing", "remove every garment", "quitar toda la ropa", "quita toda la ropa",
        "completely different outfit", "full transformation",
    )
    radical = any(term in text for term in radical_change_terms)
    requires_rebuild = bool(pose or actions or radical)
    magnitude = "structural" if requires_rebuild else ("radical" if radical else "local")

    return TextIntentContract(
        actions=tuple(actions),
        objects=tuple(objects),
        pose_constraints=tuple(pose),
        prompt_constraints=tuple(constraints),
        forbidden_additions=forbidden,
        change_magnitude=magnitude,
        requires_structural_rebuild=requires_rebuild,
    )
'''
    write(core / "intent_contract.py", intent_contract)

    compliance = r'''from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ComplianceDimension:
    status: str  # pass|fail|unknown
    reason: str
    measured: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ComplianceResult:
    image_validity: ComplianceDimension
    identity: ComplianceDimension
    pose: ComplianceDimension
    action: ComplianceDimension
    objects: ComplianceDimension
    anatomy: ComplianceDimension
    censor_artifact: ComplianceDimension
    retry_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "image_validity": self.image_validity.to_dict(),
            "identity": self.identity.to_dict(),
            "pose": self.pose.to_dict(),
            "action": self.action.to_dict(),
            "objects": self.objects.to_dict(),
            "anatomy": self.anatomy.to_dict(),
            "censor_artifact": self.censor_artifact.to_dict(),
            "retry_reasons": list(self.retry_reasons),
        }


def unknown(reason: str) -> ComplianceDimension:
    return ComplianceDimension("unknown", reason, False)


def from_known_signals(*, image_valid: bool, identity_score: float | None = None, identity_threshold: float = 85.0) -> ComplianceResult:
    validity = ComplianceDimension("pass" if image_valid else "fail", "output image validation", True)
    if identity_score is None:
        identity = unknown("identity score unavailable")
    else:
        identity = ComplianceDimension("pass" if identity_score >= identity_threshold else "fail", f"identity={identity_score:.2f}", True)
    reasons: list[str] = []
    if validity.status == "fail":
        reasons.append("invalid output image")
    if identity.status == "fail":
        reasons.append("identity below threshold")
    # Never fabricate visual compliance. Pose/action/object/anatomy require a real visual signal
    # (future VLM/pose detector or human review) and remain unknown until measured.
    return ComplianceResult(
        image_validity=validity,
        identity=identity,
        pose=unknown("no reliable visual pose evaluator available"),
        action=unknown("no reliable visual action evaluator available"),
        objects=unknown("no reliable visual object-count evaluator available"),
        anatomy=unknown("no reliable visual anatomy evaluator available"),
        censor_artifact=unknown("no reliable visual censor-artifact detector available"),
        retry_reasons=tuple(reasons),
    )


def correction_directive(issue_codes: list[str]) -> str:
    mapping = {
        "pose": "Prioritize the requested pose over the source body layout; rebuild the body configuration coherently.",
        "action": "Make the requested action physically explicit with correct contact and occlusion.",
        "objects": "Use exactly the requested number of objects and remove duplicates or extras.",
        "anatomy": "Regenerate one coherent body with exactly two arms and two legs and no duplicated limbs.",
        "censor_artifact": "Remove any artificial bar, patch, seam, covering or unrequested garment introduced by the application.",
        "identity": "Restore the registered facial identity without changing the requested pose/action.",
    }
    return " ".join(mapping[c] for c in issue_codes if c in mapping)
'''
    write(core / "compliance.py", compliance)

    test = r'''from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from v12_core.intent_contract import extract_text_contract
from v12_core.compliance import from_known_signals, correction_directive


class Maint4GeneralComplianceTests(unittest.TestCase):
    def test_01_single_drink_defaults_to_one(self):
        c = extract_text_contract("tomando cerveza en un balcón")
        self.assertTrue(any(o.name == "beer drink" and o.count == 1 for o in c.objects))

    def test_02_explicit_two_objects_preserved(self):
        c = extract_text_contract("holding two books")
        self.assertTrue(any(o.count == 2 for o in c.objects))

    def test_03_raised_leg_is_structural(self):
        c = extract_text_contract("una pierna levantada")
        self.assertTrue(c.requires_structural_rebuild)
        self.assertTrue(any("one leg raised" in p.lower() for p in c.pose_constraints))

    def test_04_sitting_is_structural(self):
        self.assertTrue(extract_text_contract("sentada en una silla").requires_structural_rebuild)

    def test_05_driving_is_structural(self):
        c = extract_text_contract("conduciendo un auto con ambas manos en el volante")
        self.assertTrue(c.requires_structural_rebuild)
        self.assertIn("driving", c.actions)

    def test_06_simple_color_edit_not_structural(self):
        c = extract_text_contract("cambia el blazer azul a rojo")
        self.assertFalse(c.requires_structural_rebuild)

    def test_07_no_unrequested_censoring_constraint(self):
        c = extract_text_contract("standing on a terrace")
        joined = " ".join(c.prompt_constraints).lower()
        self.assertIn("do not add censor bars", joined)

    def test_08_anatomy_constraint_present(self):
        c = extract_text_contract("dancing on a stage")
        joined = " ".join(c.prompt_constraints).lower()
        self.assertIn("exactly two arms and two legs", joined)

    def test_09_compliance_does_not_fabricate_pose_score(self):
        r = from_known_signals(image_valid=True, identity_score=91.0)
        self.assertEqual(r.pose.status, "unknown")
        self.assertFalse(r.pose.measured)

    def test_10_directed_retry_objects(self):
        self.assertIn("exactly the requested number", correction_directive(["objects"]))

    def test_11_directed_retry_pose(self):
        self.assertIn("requested pose", correction_directive(["pose"]))

    def test_12_identity_failure_is_measured(self):
        r = from_known_signals(image_valid=True, identity_score=70.0)
        self.assertEqual(r.identity.status, "fail")
        self.assertIn("identity below threshold", r.retry_reasons)


if __name__ == "__main__":
    unittest.main()
'''
    write(app / "test_v12_maint4.py", test)

    benchmark = r'''from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

BASE = "http://127.0.0.1:42012"
ROOT = Path(__file__).resolve().parent
OUT_DIR = ROOT / "data" / "benchmarks" / f"maint4_{int(time.time())}"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CASES = [
    ("01_simple_scene", "standing on a rooftop at sunset, looking at the camera"),
    ("02_single_drink", "drinking one glass of beer on a balcony, exactly one glass"),
    ("03_one_leg_raised", "balancing with one leg raised on a terrace"),
    ("04_sitting_book", "sitting in a chair holding exactly one red book"),
    ("05_arms_overhead", "standing with both arms raised overhead, hands visible"),
    ("06_kneeling", "kneeling beside a sofa with both hands visible"),
    ("07_mild_clothing", "change the blazer color to red while preserving the current pose"),
    ("08_full_outfit", "replace the entire outfit with a long green evening gown"),
    ("09_outfit_high_kick", "replace the entire outfit with athletic clothing and perform one high kick"),
    ("10_driving", "driving a car with both hands on exactly one steering wheel"),
]


def get_character(client: httpx.Client) -> str | None:
    try:
        r = client.get(f"{BASE}/api/characters", timeout=20)
        r.raise_for_status()
        data = r.json()
        rows = data.get("characters") if isinstance(data, dict) else data
        if isinstance(rows, list) and rows:
            first = rows[0]
            if isinstance(first, dict):
                return first.get("id") or first.get("character_id")
    except Exception:
        return None
    return None


def poll(client: httpx.Client, job_id: str, timeout_s: int = 900) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = client.get(f"{BASE}/api/jobs/{job_id}", timeout=30)
        r.raise_for_status()
        data = r.json()
        if data.get("status") in {"complete", "completed", "done", "failed", "error", "cancelled"}:
            return data
        time.sleep(2.0)
    raise TimeoutError(job_id)


def find_output(job_id: str) -> Path | None:
    out = ROOT / "data" / "outputs"
    candidates = sorted(out.glob(f"{job_id}_*.png"))
    return candidates[0] if candidates else None


def make_sheet(rows: list[dict]) -> Path:
    thumbs = []
    for row in rows:
        p = row.get("output_path")
        if not p:
            continue
        path = Path(p)
        if not path.is_file():
            continue
        img = Image.open(path).convert("RGB")
        img.thumbnail((320, 420))
        thumbs.append((row["name"], img.copy()))
    w = 680
    h = max(1, (len(thumbs) + 1) // 2) * 470
    sheet = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(sheet)
    for idx, (name, img) in enumerate(thumbs):
        col, row = idx % 2, idx // 2
        x, y = col * 340 + 10, row * 470 + 30
        draw.text((x, y - 20), name, fill="black")
        sheet.paste(img, (x, y))
    path = OUT_DIR / "contact_sheet.jpg"
    sheet.save(path, quality=90)
    return path


def main() -> int:
    rows: list[dict] = []
    with httpx.Client() as client:
        health = client.get(f"{BASE}/api/health", timeout=20)
        health.raise_for_status()
        character_id = get_character(client)
        print(f"CHARACTER_ID={character_id}")
        for name, prompt in CASES:
            payload = {
                "prompt": prompt,
                "aspect": "portrait",
                "mode": "auto",
                "denoise": 0.58,
                "identity_strength": 94,
                "identity_lock": True,
                "count": 1,
            }
            if character_id:
                payload["character_id"] = character_id
            started = time.time()
            r = client.post(f"{BASE}/api/generate", json=payload, timeout=60)
            r.raise_for_status()
            created = r.json()
            job_id = created.get("job_id") or created.get("id")
            if not job_id:
                raise RuntimeError(f"No job id for {name}: {created}")
            final = poll(client, job_id)
            output = find_output(job_id)
            plan = final.get("pipeline_plan") or {}
            contract = final.get("intent_contract") or final.get("prompt_contract", {}).get("intent_contract") or {}
            row = {
                "name": name,
                "prompt": prompt,
                "job_id": job_id,
                "status": final.get("status"),
                "resolved_mode": final.get("resolved_mode") or final.get("mode"),
                "pipeline": plan.get("pipeline"),
                "execution_strategy": plan.get("execution_strategy"),
                "effective_denoise": plan.get("effective_denoise") or final.get("effective_denoise") or final.get("denoise"),
                "requires_structural_rebuild": contract.get("requires_structural_rebuild"),
                "output_path": str(output) if output else None,
                "seconds": round(time.time() - started, 2),
            }
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False))
    report = OUT_DIR / "report.json"
    report.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    sheet = make_sheet(rows)
    print(f"REPORT={report}")
    print(f"CONTACT_SHEET={sheet}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''
    write(app / "benchmark_v12_maint4.py", benchmark)

    patch_main(app / "main.py")
    print("MAINT4_PATCH_APPLIED")


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: maint4_general_compliance_patch.py <CCS_ROOT>", file=sys.stderr)
        return 2
    patch(Path(sys.argv[1]).resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
