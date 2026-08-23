from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

SAFE_KEYS = {
    "job_id", "status", "created_at", "updated_at", "prompt", "original_prompt",
    "translated_prompt", "compiled_prompt", "mode", "resolved_mode", "aspect", "seed",
    "denoise", "effective_denoise", "identity_strength", "identity_lock", "action_id",
    "intent", "pipeline_plan", "evaluation_v12", "clothing_change_intensity",
    "pose_change_intensity", "localized_clothing_mask", "retry_count", "selected_attempt",
    "attempts", "error", "progress", "message",
}


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if k in SAFE_KEYS:
                out[k] = sanitize(v)
        return out
    if isinstance(value, list):
        return [sanitize(v) for v in value[:5]]
    if isinstance(value, str):
        return value[:2000]
    return value


def load_candidates(root: Path) -> list[tuple[float, Path, dict[str, Any]]]:
    dirs = [root / "app" / "data" / "jobs", root / "app" / "data" / "outputs"]
    found: list[tuple[float, Path, dict[str, Any]]] = []
    for d in dirs:
        if not d.is_dir():
            continue
        for p in d.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
            except Exception:
                continue
            prompt = str(data.get("prompt") or data.get("original_prompt") or "")
            if prompt or "pipeline_plan" in data or "intent" in data:
                found.append((p.stat().st_mtime, p, data))
    found.sort(key=lambda x: x[0], reverse=True)
    return found


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: inspect_latest_jobs.py <root> [root2 ...]", file=sys.stderr)
        return 2
    for raw in sys.argv[1:]:
        root = Path(raw)
        print(f"=== ROOT {root} ===")
        rows = load_candidates(root)
        print(f"CANDIDATES={len(rows)}")
        for _, path, data in rows[:8]:
            print(f"--- {path.name} ---")
            print(json.dumps(sanitize(data), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
