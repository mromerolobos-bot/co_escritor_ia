from pathlib import Path
import sys

p = Path(sys.argv[1] if len(sys.argv) > 1 else 'test_bridge.py')
t = p.read_text(encoding='utf-8')
if '_is_gui_command,' not in t:
    t = t.replace('    run_command_safe,\n', '    run_command_safe,\n    _is_gui_command,\n', 1)
t = t.replace('bridge.run_command_safe(', 'run_command_safe(')
t = t.replace('bridge._is_gui_command(', '_is_gui_command(')
p.write_text(t, encoding='utf-8')
print('TEST_IMPORTS_FIXED:', p)
