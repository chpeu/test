#!/usr/bin/env python3
from pathlib import Path

text = Path('core/position/analytics_logger.py').read_text()
start = text.split('trade_data = {', 1)
if len(start) < 2:
    raise SystemExit('trade_data dict not found')
rest = start[1]
stack = 1
collected = []
for ch in rest:
    if ch == '{':
        stack += 1
    elif ch == '}':
        stack -= 1
        if stack == 0:
            break
    collected.append(ch)

dict_body = ''.join(collected)
keys = []
current = ''
in_key = True
line_no = 0
for line in dict_body.split('\n'):
    line_no += 1
    stripped = line.strip()
    if not stripped or stripped.startswith('#'):
        continue
    if ':' not in stripped:
        continue
    key = stripped.split(':', 1)[0].strip()
    if key.startswith("'") and key.endswith("'"):
        key = key[1:-1]
    elif key.startswith('"') and key.endswith('"'):
        key = key[1:-1]
    keys.append(key)

print(f"Total keys: {len(keys)}")
for i, key in enumerate(keys, 1):
    print(f"{i:3}. {key}")
