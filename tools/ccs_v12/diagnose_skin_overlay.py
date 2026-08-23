from __future__ import annotations
import json, os, re, sys
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd().resolve()
PATTERNS = [
    r"skin", r"tone", r"clothes", r"clothing", r"garment", r"mask", r"inpaint",
    r"composite", r"segformer", r"clipseg", r"coverage", r"opaque", r"beige",
    r"shorts", r"bodysuit", r"preserve", r"edit", r"identity", r"style_transfer",
]
RX = re.compile("|".join(PATTERNS), re.I)
TEXT_EXT = {'.py','.js','.html','.css','.json','.md','.txt'}
TARGETS = [ROOT/'app'/'main.py', ROOT/'app'/'identity.py']
TARGETS += sorted((ROOT/'app'/'v12_core').glob('*.py')) if (ROOT/'app'/'v12_core').exists() else []
if (ROOT/'app'/'workflows').exists(): TARGETS += sorted((ROOT/'app'/'workflows').glob('*.json'))
TARGETS += [ROOT/'app'/'static'/'app.js', ROOT/'app'/'static'/'index.html']

def emit_hits(path: Path):
    try:
        lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
    except Exception as e:
        print(f"READ_ERROR {path}: {e}")
        return
    hits=[]
    for i,line in enumerate(lines,1):
        if RX.search(line): hits.append(i)
    if not hits: return
    print(f"\n=== FILE {path.relative_to(ROOT)} ===")
    shown=set()
    for n in hits:
        a=max(1,n-2); b=min(len(lines),n+2)
        key=(a,b)
        if key in shown: continue
        shown.add(key)
        print(f"-- lines {a}-{b} --")
        for j in range(a,b+1):
            s=lines[j-1]
            if len(s)>360: s=s[:360]+'...'
            print(f"{j}: {s}")

print(f"ROOT={ROOT}")
for p in TARGETS:
    if p.exists() and p.suffix.lower() in TEXT_EXT:
        emit_hits(p)

jobs_dir = ROOT/'app'/'data'/'jobs'
print("\n=== RECENT JOB SUMMARIES ===")
if jobs_dir.exists():
    files = sorted(jobs_dir.glob('*.json'), key=lambda p:p.stat().st_mtime, reverse=True)[:12]
    for p in files:
        try:
            d=json.loads(p.read_text(encoding='utf-8', errors='replace'))
        except Exception as e:
            print(f"JOB_READ_ERROR {p.name}: {e}")
            continue
        req=d.get('request') or d.get('generation_request') or {}
        prompt=req.get('prompt') if isinstance(req,dict) else None
        if isinstance(prompt,str) and len(prompt)>240: prompt=prompt[:240]+'...'
        out={
            'file':p.name,
            'status':d.get('status'),
            'character_id':d.get('character_id') or (req.get('character_id') if isinstance(req,dict) else None),
            'mode':req.get('mode') if isinstance(req,dict) else None,
            'prompt':prompt,
            'intent':d.get('intent'),
            'pipeline_plan':d.get('pipeline_plan'),
            'outputs':d.get('outputs'),
            'attempts':d.get('attempts'),
            'selected_attempt':d.get('selected_attempt'),
        }
        print(json.dumps(out, ensure_ascii=False, default=str))
else:
    print('NO_JOBS_DIR')

print("\nDIAG_DONE")
