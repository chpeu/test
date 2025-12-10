#!/usr/bin/env python3
import re

with open('core/analytics_database.py', 'r', encoding='utf-8') as f:
    sql = f.read()

match = re.search(r'INSERT INTO trades \((.*?)\) VALUES', sql, re.DOTALL)
cols = []
if match:
    text = re.sub(r'--.*', '', match.group(1))
    cols = [c.strip() for c in text.split(',') if c.strip()]
else:
    raise SystemExit('Insert columns not found')

with open('core/position/analytics_logger.py', 'r', encoding='utf-8') as f:
    py = f.read()

match = re.search(r'trade_data\s*=\s*{(.*?)}\s*$', py, re.DOTALL)
if not match:
    raise SystemExit('trade_data dict not found')

text = match.group(1)
# Remove comments
text = re.sub(r"#.*", '', text)
# Split entries
entries = []
for line in text.split('\n'):
    line = line.strip()
    if not line:
        continue
    if ':' in line:
        key = line.split(':', 1)[0].strip().strip("'\"")
        entries.append(key)

missing = [c for c in cols if c not in entries]
extra = [e for e in entries if e not in cols]

print(f'Total columns SQL: {len(cols)}')
print(f'Total keys trade_data: {len(entries)}')
print('\nMissing columns:')
for m in missing:
    print('-', m)

print('\nExtra keys:')
for e in extra:
    print('-', e)
