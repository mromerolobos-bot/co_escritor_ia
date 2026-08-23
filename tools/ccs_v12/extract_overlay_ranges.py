from __future__ import annotations
import sys
from pathlib import Path
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='backslashreplace')
except Exception:
    pass
root=Path(sys.argv[1]).resolve()
p=root/'app'/'main.py'
lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
for a,b in [(330,410),(840,940),(940,1010)]:
    print(f'=== RANGE {a}-{b} ===')
    for i in range(a,min(b,len(lines))+1):
        s=lines[i-1]
        if len(s)>500:s=s[:500]+'...'
        print(f'{i}: {s}')
print('RANGES_DONE')
