from pathlib import Path
import shutil, json, os, time

SRC = Path(r"C:\pinokio\api\cinematic-character-studio-v1-1")
BASE = Path(r"C:\Users\Chelowolf\CinematicCharacterStudioV12_Working")
EXCLUDE = {"env", "models", "__pycache__", "logs", ".git"}

if not SRC.is_dir():
    raise SystemExit(f"SOURCE_NOT_FOUND: {SRC}")

DST = BASE
if DST.exists():
    stamp = time.strftime("%Y%m%d_%H%M%S")
    DST = Path(str(BASE) + "_" + stamp)


def ignore_names(_dir, names):
    return [n for n in names if n in EXCLUDE or n.endswith('.pyc')]

shutil.copytree(SRC, DST, ignore=ignore_names)
analysis = DST / "_analysis"
analysis.mkdir(exist_ok=True)

files = []
total = 0
for p in DST.rglob('*'):
    if p.is_file():
        try:
            size = p.stat().st_size
        except OSError:
            size = 0
        total += size
        files.append({"path": str(p.relative_to(DST)), "bytes": size})

files_sorted = sorted(files, key=lambda x: x['bytes'], reverse=True)
key_candidates = [
    "VERSION", "README.md", "AGENTS.md", "CLAUDE.md", "GEMINI.md",
    "app/main.py", "app/identity.py", "app/requirements.txt", "app/test_core.py"
]
manifest = {
    "source": str(SRC),
    "working_copy": str(DST),
    "excluded_names": sorted(EXCLUDE),
    "file_count": len(files),
    "total_bytes": total,
    "top_level": sorted([p.name for p in DST.iterdir()]),
    "key_files": {k: (DST / k).is_file() for k in key_candidates},
    "largest_files": files_sorted[:40],
}
(analysis / "inventory.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

tree_lines = []
for p in sorted(DST.rglob('*')):
    try:
        rel = p.relative_to(DST)
    except ValueError:
        continue
    depth = len(rel.parts) - 1
    if depth <= 4:
        tree_lines.append(("  " * depth) + ("[D] " if p.is_dir() else "[F] ") + p.name)
    if len(tree_lines) >= 2500:
        tree_lines.append("...TRUNCATED...")
        break
(analysis / "tree.txt").write_text("\n".join(tree_lines), encoding="utf-8")

print(f"COPY_READY: {DST}")
print(f"INVENTORY: {analysis / 'inventory.json'}")
print(f"TREE: {analysis / 'tree.txt'}")
print(f"FILES: {len(files)}")
print(f"BYTES: {total}")
