from __future__ import annotations

import hashlib
import shutil
import sys
from datetime import datetime
from pathlib import Path

RUNTIME_FILES = [
    Path("app/main.py"),
    Path("app/v12_core/intent.py"),
    Path("app/v12_core/router.py"),
    Path("app/v12_core/actions.py"),
    Path("app/test_v12_phase4.py"),
]

POST_MAINT_TESTS = [
    Path("app/test_v12_maint2.py"),
    Path("app/test_v12_maint3.py"),
]

MUTABLE_PREFIXES = (
    "app/data/",
    "app/data\\",
    "logs/",
    "logs\\",
    "models/",
    "models\\",
    "env/",
    "env\\",
)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def assert_safe_source(source: Path) -> None:
    required = [source / "app/main.py", source / "app/v12_core/router.py", source / "app/v12_core/intent.py"]
    missing = [str(p) for p in required if not p.is_file()]
    if missing:
        raise RuntimeError("Base V1.2 staging is incomplete; missing: " + ", ".join(missing))
    low = str(source).lower().replace("/", "\\")
    if "cinematic-character-studio-v1-2" not in low:
        raise RuntimeError(f"Refusing unexpected restore source: {source}")


def restore_target(source: Path, target: Path, backup_root: Path) -> None:
    if not (target / "app").is_dir():
        raise RuntimeError(f"Target is not a CCS V1.2 tree: {target}")

    print(f"=== RESTORE TARGET {target} ===")
    for rel in RUNTIME_FILES:
        src = source / rel
        dst = target / rel
        if not src.is_file():
            print(f"SKIP_MISSING_BASE {rel}")
            continue

        # Runtime-only restore: never touch mutable app/data, models, env, logs, or user content.
        rel_text = str(rel)
        if rel_text.startswith(MUTABLE_PREFIXES):
            raise RuntimeError(f"Refusing mutable path: {rel}")

        if dst.exists():
            backup = backup_root / target.name / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(dst, backup)
            print(f"BACKUP {dst} -> {backup}")

        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        print(f"RESTORED {rel} sha256={sha256(dst)} base_sha256={sha256(src)}")
        if sha256(dst) != sha256(src):
            raise RuntimeError(f"Hash mismatch after restore: {dst}")

    for rel in POST_MAINT_TESTS:
        p = target / rel
        if p.exists():
            backup = backup_root / target.name / rel
            backup.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(backup))
            print(f"REMOVED_POST_MAINT_FILE {rel} -> {backup}")


def main() -> int:
    if len(sys.argv) != 4:
        print("usage: restore_v12_base_runtime.py <base_staging> <working_copy> <installed_v12>", file=sys.stderr)
        return 2

    source = Path(sys.argv[1]).resolve()
    working = Path(sys.argv[2]).resolve()
    installed = Path(sys.argv[3]).resolve()
    assert_safe_source(source)

    # Hard safety guard: V1.1 must never be a target.
    for target in (working, installed):
        low = str(target).lower().replace("/", "\\")
        if "cinematic-character-studio-v1-1" in low:
            raise RuntimeError(f"Refusing V1.1 target: {target}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_root = working / "_rollback_backup" / f"before_restore_{stamp}"
    backup_root.mkdir(parents=True, exist_ok=True)
    print(f"BACKUP_ROOT={backup_root}")

    restore_target(source, working, backup_root)
    restore_target(source, installed, backup_root)

    print("RESTORE_V12_BASE_RUNTIME_OK")
    print("MUTABLE_DATA_PRESERVED=app/data, models, env, logs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
