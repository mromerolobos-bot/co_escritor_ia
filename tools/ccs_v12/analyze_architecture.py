from pathlib import Path
import ast, json, re

ROOT = Path(r"C:\Users\Chelowolf\CinematicCharacterStudioV12_Working")
OUT = ROOT / "_analysis" / "architecture_report.json"


def analyze_py(rel):
    path = ROOT / rel
    text = path.read_text(encoding="utf-8", errors="replace")
    tree = ast.parse(text)
    imports, funcs, classes, globals_ = [], [], [], []
    for node in tree.body:
        if isinstance(node, ast.Import):
            imports += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imports.append((node.module or "") + ":" + ",".join(a.name for a in node.names))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            decs=[]
            for d in node.decorator_list:
                try: decs.append(ast.unparse(d))
                except Exception: decs.append(type(d).__name__)
            calls=[]
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call):
                    try: calls.append(ast.unparse(sub.func))
                    except Exception: pass
            funcs.append({
                "name": node.name,
                "async": isinstance(node, ast.AsyncFunctionDef),
                "line_start": node.lineno,
                "line_end": getattr(node, "end_lineno", node.lineno),
                "lines": getattr(node, "end_lineno", node.lineno)-node.lineno+1,
                "decorators": decs,
                "calls_sample": sorted(set(calls))[:30],
            })
        elif isinstance(node, ast.ClassDef):
            classes.append({"name":node.name,"line":node.lineno,"bases":[ast.unparse(b) for b in node.bases]})
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            names=[]
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for t in targets:
                if isinstance(t, ast.Name): names.append(t.id)
            globals_ += names
    endpoints=[]
    for f in funcs:
        for d in f["decorators"]:
            m=re.search(r'app\.(get|post|put|delete|patch)\((.+)\)', d)
            if m:
                endpoints.append({"method":m.group(1).upper(),"route_expr":m.group(2),"function":f["name"],"line":f["line_start"]})
    return {
        "path": rel,
        "chars": len(text),
        "lines": text.count("\n")+1,
        "imports": imports,
        "classes": classes,
        "globals": globals_,
        "functions": funcs,
        "endpoints": endpoints,
        "large_functions": [f for f in funcs if f["lines"] >= 80],
    }

main = analyze_py("app/main.py")
identity = analyze_py("app/identity.py")
js=(ROOT/"app/static/app.js").read_text(encoding="utf-8",errors="replace")
html=(ROOT/"app/static/index.html").read_text(encoding="utf-8",errors="replace")
req=(ROOT/"app/requirements.txt").read_text(encoding="utf-8",errors="replace")

js_api=sorted(set(re.findall(r'[\"\'](/api/[^\"\']*)[\"\']', js)))
js_funcs=sorted(set(re.findall(r'(?:async\s+)?function\s+([A-Za-z0-9_]+)\s*\(', js)))
html_ids=sorted(set(re.findall(r'id=[\"\']([^\"\']+)', html)))

report={
    "root": str(ROOT),
    "python": {"main":main,"identity":identity},
    "frontend": {"app_js_chars":len(js),"functions":js_funcs,"api_routes_literal":js_api,"html_ids":html_ids},
    "requirements": [x.strip() for x in req.splitlines() if x.strip() and not x.strip().startswith('#')],
}
OUT.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
print(f"ARCH_REPORT: {OUT}")
print(f"MAIN_LINES: {main['lines']} FUNCTIONS: {len(main['functions'])} ENDPOINTS: {len(main['endpoints'])}")
print(f"IDENTITY_LINES: {identity['lines']} FUNCTIONS: {len(identity['functions'])}")
print(f"JS_FUNCTIONS: {len(js_funcs)}")
