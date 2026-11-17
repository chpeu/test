f=open('core/analytics_database.py','r',encoding='utf-8').read()
start=f.find("''', (", f.find('INSERT INTO trades'))
end=f.find('))', start)
values_block=f[start:end]

# Count commas in the values tuple
comma_count = values_block.count(',')
print(f'Comma count in values tuple: {comma_count}')
print(f'Estimated values: {comma_count + 1}')

# Also manually count trade.get lines
get_lines = [l for l in values_block.split('\n') if 'trade.get' in l or 'self.instance_port' in l or '_json' in l]
print(f'Lines with values: {len(get_lines)}')
