from __future__ import annotations
import ast, json, os, re, sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
    sys.stderr.reconfigure(encoding='utf-8', errors='backslashreplace')
except Exception:
    pass
ROOT=Path(sys.argv[1]).resolve()
P=ROOT/'app'/'main.py'
text=P.read_text(encoding='utf-8',errors='replace')
lines=text.splitlines()
strong=re.compile(r"Segformer|CLIPSeg|VAEEncodeForInpaint|ImageCompositeMasked|GrowMask|FeatherMask|clothing.remov|remove.cloth|remove.*garment|WAI|Illustrious|nsfw|mask_prompt|clothes_mask|garment_mask|skin.*mask|inpaint|coverage|opaque",re.I)
print(f'ROOT={ROOT}')
print('=== STRONG HITS main.py ===')
hits=[]
for i,l in enumerate(lines,1):
    if strong.search(l): hits.append(i)
merged=[]
for n in hits:
    a=max(1,n-6); b=min(len(lines),n+8)
    if merged and a<=merged[-1][1]+1: merged[-1]=(merged[-1][0],max(merged[-1][1],b))
    else: merged.append((a,b))
for a,b in merged:
    print(f'-- lines {a}-{b} --')
    for j in range(a,b+1):
        s=lines[j-1]
        if len(s)>500:s=s[:500]+'...'
        print(f'{j}: {s}')

print('\n=== FUNCTIONS CONTAINING STRONG HITS ===')
try:
    tree=ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)):
            seg='\n'.join(lines[node.lineno-1:getattr(node,'end_lineno',node.lineno)])
            if strong.search(seg):
                print(f'{node.name}: lines {node.lineno}-{getattr(node,"end_lineno",node.lineno)}')
except Exception as e: print('AST_ERROR',repr(e))

print('\n=== RECENT JOBS WITH CLOTHING/EDIT SIGNALS ===')
jobs=ROOT/'app'/'data'/'jobs'
if jobs.exists():
    for p in sorted(jobs.glob('*.json'),key=lambda x:x.stat().st_mtime,reverse=True)[:30]:
        try:d=json.loads(p.read_text(encoding='utf-8',errors='replace'))
        except Exception:continue
        blob=json.dumps(d,ensure_ascii=False,default=str)
        if re.search(r"clothing|clothes|garment|remove|edit|inpaint|mask|shorts|bikini|swim",blob,re.I):
            req=d.get('request') or d.get('generation_request') or {}
            prompt=req.get('prompt') if isinstance(req,dict) else None
            if isinstance(prompt,str) and len(prompt)>300:prompt=prompt[:300]+'...'
            out={'job':p.stem,'status':d.get('status'),'prompt':prompt,'mode':req.get('mode') if isinstance(req,dict) else None,'intent':d.get('intent'),'pipeline_plan':d.get('pipeline_plan'),'selected_attempt':d.get('selected_attempt'),'outputs':d.get('outputs')}
            print(json.dumps(out,ensure_ascii=False,default=str))
print('DIAG_V2_DONE')
