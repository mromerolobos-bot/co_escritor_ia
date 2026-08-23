from __future__ import annotations
import sys
from pathlib import Path
try: sys.stdout.reconfigure(encoding='utf-8',errors='backslashreplace')
except Exception: pass
root=Path(sys.argv[1]).resolve(); lines=(root/'app'/'main.py').read_text(encoding='utf-8',errors='replace').splitlines()
for i in range(897,min(936,len(lines))+1):
 s=lines[i-1]
 if len(s)>700:s=s[:700]+'...'
 print(f'{i}: {s}')
