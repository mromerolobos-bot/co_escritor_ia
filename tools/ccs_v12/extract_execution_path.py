from __future__ import annotations
import ast, sys
from pathlib import Path

TARGET_FUNCS = {
    'build_prompt_contract','compile_prompt','build_workflow','build_identity_refine_workflow',
    'run_generation','generate','route_pipeline','parse_generation_intent'
}

def dump_file(path: Path):
    text = path.read_text(encoding='utf-8')
    tree = ast.parse(text)
    lines = text.splitlines()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in TARGET_FUNCS:
            end = getattr(node, 'end_lineno', node.lineno)
            print(f'=== {path.name}:{node.name} lines {node.lineno}-{end} ===')
            print('\n'.join(f'{i}: {lines[i-1]}' for i in range(node.lineno, end+1)))


def main():
    root=Path(sys.argv[1])
    dump_file(root/'app'/'main.py')
    dump_file(root/'app'/'v12_core'/'router.py')
    dump_file(root/'app'/'v12_core'/'intent.py')

if __name__=='__main__': main()
