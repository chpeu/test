
import os

def fix_position_manager():
    path = "core/position_manager.py"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        # Fix the specific broken line with backslash escape
        if "get_effective_value(\\'trading_circuit_breaker_enabled\\')" in line:
            line = line.replace("\\'trading_circuit_breaker_enabled\\'", "'trading_circuit_breaker_enabled'")
        
        # Also fix any other possible broken get_effective_value calls with backslashes
        line = line.replace("\\'tp_sl_mode\\'", "'tp_sl_mode'")
        
        new_lines.append(line)
            
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(new_lines)
    print(f"Fixed syntax in {path}")

if __name__ == "__main__":
    fix_position_manager()
    
    import py_compile
    try:
        py_compile.compile("core/position_manager.py", doraise=True)
        print("core/position_manager.py: Syntax OK")
    except Exception as e:
        print(f"core/position_manager.py: Syntax Error: {e}")
