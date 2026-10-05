
import os
import re

def fix_position_manager_syntax():
    path = "core/position_manager.py"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    i = 0
    while i < len(lines):
        line = lines[i]
        # Fix line 4083 area (excessive indentation for try)
        if "# 🔥 FIX 10/12/2025: Ne récupérer l'état CB que s'il est activé" in line:
            fixed_lines.append(line)
            # Find the next 'try:' which might be misindented
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("try:"):
                fixed_lines.append(lines[j])
                j += 1
            if j < len(lines) and lines[j].strip().startswith("try:"):
                # Re-indent the try block correctly (20 spaces based on surrounding context)
                fixed_lines.append("                    try:\n")
                i = j + 1
                continue
        
        # General indentation fix for common patterns I might have broken
        # Replace tabs if any (should already be done)
        line = line.replace('\t', '    ')
        fixed_lines.append(line)
        i += 1
            
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(fixed_lines)
    print(f"Applied manual syntax fixes to {path}")

def fix_analyzer_syntax():
    path = "core/analyzer.py"
    if not os.path.exists(path):
        return
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = [line.replace('\t', '    ') for line in lines]
    
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.writelines(fixed_lines)
    print(f"Normalized {path}")

if __name__ == "__main__":
    fix_position_manager_syntax()
    fix_analyzer_syntax()
    
    import py_compile
    try:
        py_compile.compile("core/analyzer.py", doraise=True)
        print("core/analyzer.py: Syntax OK")
    except Exception as e:
        print(f"core/analyzer.py: Syntax Error: {e}")
        
    try:
        py_compile.compile("core/position_manager.py", doraise=True)
        print("core/position_manager.py: Syntax OK")
    except Exception as e:
        print(f"core/position_manager.py: Syntax Error: {e}")
