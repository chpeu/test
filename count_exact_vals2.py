f = open('core/analytics_database.py', 'r', encoding='utf-8').readlines()

# Find start and end of VALUES tuple
start_idx = None
end_idx = None
for i, line in enumerate(f):
    if "''', (" in line:
        start_idx = i + 1
        print(f"Found start at line {i+1}: {line.strip()}")
    if start_idx and '))' in line and not line.strip().startswith('#'):
        end_idx = i
        print(f"Found end at line {i+1}: {line.strip()}")
        break

if start_idx and end_idx:
    values_lines = f[start_idx:end_idx]
    # Count actual values
    value_count = 0
    for line in values_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            if 'trade.get(' in stripped or '_json' in stripped or 'self.instance_port' in stripped or 'config_hash' in stripped:
                value_count += 1
    
    print(f"\nTotal values found: {value_count}")
else:
    print("Could not find complete VALUES tuple")
