f = open('core/analytics_database.py', 'r', encoding='utf-8').readlines()

# Start from line 780 (index 779)
start_idx = 780
end_idx = 896

values_lines = f[start_idx:end_idx+1]

# Count actual values (lines with trade.get, _json, self.instance_port, config_hash)
value_count = 0
values_list = []
for line in values_lines:
    stripped = line.strip()
    if stripped and not stripped.startswith('#') and not stripped == '))':
        if ('trade.get(' in stripped or 
            '_json' in stripped or 
            'self.instance_port' in stripped or 
            'config_hash' in stripped):
            value_count += 1
            # Extract the value name
            if 'trade.get(' in stripped:
                start = stripped.find("'") + 1
                end = stripped.find("'", start)
                val_name = stripped[start:end] if start > 0 and end > start else stripped[:30]
            elif 'self.instance_port' in stripped:
                val_name = 'instance_port'
            elif '_json' in stripped:
                val_name = stripped.split('=')[0].strip() if '=' in stripped else stripped[:30]
            else:
                val_name = stripped[:30]
            values_list.append(val_name)

print(f"Total values found: {value_count}")
print(f"\nFirst 20 values:")
for i, v in enumerate(values_list[:20], 1):
    print(f"  {i}. {v}")
print(f"\nLast 20 values:")
for i, v in enumerate(values_list[-20:], len(values_list)-19):
    print(f"  {i}. {v}")
