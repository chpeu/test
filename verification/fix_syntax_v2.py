
import os
import re

def fix_file_indentation(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for line in lines:
        # Replace tabs with 4 spaces
        line = line.replace('\t', '    ')
        # Strip trailing whitespace (but keep newline)
        line = line.rstrip() + '\n'
        fixed_lines.append(line)
        
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(fixed_lines)
    print(f"Normalized indentation and line endings in {path}")

def fix_analyzer_syntax():
    path = "core/analyzer.py"
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for i, line in enumerate(lines):
        # Specific fix for the recovery mode block which seems to be causing issues
        if "# === RECOVERY MODE PROGRESSIF ===" in line:
            new_lines.append("                # === RECOVERY MODE PROGRESSIF ===\n")
        elif "recovery_config = get_effective_value('recovery_mode') or {}" in line:
            new_lines.append("                recovery_config = get_effective_value('recovery_mode') or {}\n")
        elif "min_score_required = best_setup.get('min_score_required', get_effective_value('min_score_required') or 7.5)" in line:
            new_lines.append("                min_score_required = best_setup.get('min_score_required', get_effective_value('min_score_required') or 7.5)\n")
        elif "if recovery_config.get('enabled', False) and position_manager:" in line:
            new_lines.append("                if recovery_config.get('enabled', False) and position_manager:\n")
        else:
            new_lines.append(line)
            
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(new_lines)
    print(f"Applied specific syntax fixes to {path}")

def fix_position_manager_syntax():
    path = "core/position_manager.py"
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Use regex to fix the common indentation mistakes in try/except blocks
    # Fix the CB status block
    content = re.sub(
        r'try:\s+from utils\.effective_config import get_effective_value\s+if get_effective_value\(\'trading_circuit_breaker_enabled\'\)',
        r'                    try:\n                        from utils.effective_config import get_effective_value\n                        if get_effective_value(\'trading_circuit_breaker_enabled\')',
        content
    )
    
    # Fix the missing pass after except
    content = re.sub(r'except Exception:\s+\n', r'                except Exception:\n                    pass\n', content)
    
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)
    print(f"Applied specific syntax fixes to {path}")

if __name__ == "__main__":
    # First normalize everything
    fix_file_indentation("core/analyzer.py")
    fix_file_indentation("core/position_manager.py")
    
    # Then apply specific fixes
    fix_analyzer_syntax()
    fix_position_manager_syntax()
    
    # Run a simple syntax check
    try:
        import py_compile
        py_compile.compile("core/analyzer.py", doraise=True)
        print("core/analyzer.py: Syntax OK")
        py_compile.compile("core/position_manager.py", doraise=True)
        print("core/position_manager.py: Syntax OK")
    except Exception as e:
        print(f"Syntax check failed: {e}")
