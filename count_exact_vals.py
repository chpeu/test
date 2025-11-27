f = open('core/analytics_database.py', 'r', encoding='utf-8').readlines()

# Find start and end of VALUES tuple
start_idx = None
end_idx = None
for i, line in enumerate(f):
    if "''', (" in line and 'INSERT INTO trades' in ''.join(f[max(0, i-50):i]):
        start_idx = i + 1
    if start_idx and '))\n' == line:
        end_idx = i
        break

if start_idx and end_idx:
    values_lines = f[start_idx:end_idx]
    # Count actual values (trade.get, json variables, self.instance_port)
    value_count = 0
    for line in values_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            if 'trade.get(' in stripped or '_json' in stripped or 'self.instance_port' in stripped or 'config_hash' in stripped:
                value_count += 1
    
    print(f"Start line: {start_idx + 1}")
    print(f"End line: {end_idx + 1}")
    print(f"Total values found: {value_count}")
    
    # Show first 10 and last 10 values
    all_values = []
    for line in values_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            if 'trade.get(' in stripped or '_json' in stripped or 'self.instance_port' in stripped or 'config_hash' in stripped:
                all_values.append(stripped)
    
    print("\nFirst 10 values:")
    for v in all_values[:10]:
        print(f"  {v}")
    print("\nLast 10 values:")
    for v in all_values[-10:]:
        print(f"  {v}")
else:
    print("Could not find VALUES tuple")
