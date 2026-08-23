from pathlib import Path
import json
p=Path(r"C:\Users\Chelowolf\CinematicCharacterStudioV12_Working\_analysis\architecture_report.json")
r=json.loads(p.read_text(encoding='utf-8'))
for key in ['main','identity']:
    m=r['python'][key]
    print(f"[{key.upper()}] lines={m['lines']} chars={m['chars']}")
    print('CLASSES:', ', '.join(c['name'] for c in m['classes']))
    print('FUNCTIONS:')
    for f in m['functions']:
        dec=(' decorators='+','.join(f['decorators'])) if f['decorators'] else ''
        print(f"- {f['name']} L{f['line_start']}-{f['line_end']} ({f['lines']} lines){dec}")
    print('ENDPOINTS:')
    for e in m['endpoints']:
        print(f"- {e['method']} {e['route_expr']} -> {e['function']} L{e['line']}")
    print('LARGE_FUNCTIONS:', ', '.join(f"{f['name']}({f['lines']})" for f in m['large_functions']) or 'none')
print('[FRONTEND]')
print('FUNCTIONS:', ', '.join(r['frontend']['functions']))
print('API_LITERALS:', ', '.join(r['frontend']['api_routes_literal']))
print('[REQUIREMENTS]')
for x in r['requirements']: print('-',x)
