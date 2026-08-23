from pathlib import Path

ROOT = Path(r"C:\Users\Chelowolf\CinematicCharacterStudioV12_Working")
OUT = ROOT / "_analysis" / "source_chunks"
OUT.mkdir(parents=True, exist_ok=True)

for rel in ["app/main.py"]:
    src = ROOT / rel
    text = src.read_text(encoding="utf-8", errors="replace")
    chunk_size = 38000
    for i in range(0, len(text), chunk_size):
        part = text[i:i+chunk_size]
        dest = OUT / f"{src.stem}_{i//chunk_size+1:02d}.txt"
        dest.write_text(part, encoding="utf-8")
        print(f"CHUNK: {dest} chars={len(part)}")
    print(f"SOURCE_CHARS: {len(text)}")
