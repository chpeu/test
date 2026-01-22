
import os

def fix_analyzer():
    path = "core/analyzer.py"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    new_lines = []
    for line in lines:
        # Normalize indentation to spaces (4 spaces per level)
        # Check for the specific problematic blocks
        if "# === RECOVERY MODE PROGRESSIF ===" in line:
            new_lines.append("                # === RECOVERY MODE PROGRESSIF ===\n")
        elif "recovery_config = get_effective_value('recovery_mode') or {}" in line:
            new_lines.append("                recovery_config = get_effective_value('recovery_mode') or {}\n")
        elif "min_score_required = best_setup.get('min_score_required', get_effective_value('min_score_required') or 7.5)" in line:
            new_lines.append("                min_score_required = best_setup.get('min_score_required', get_effective_value('min_score_required') or 7.5)\n")
        else:
            new_lines.append(line)
            
    with open(path, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Fixed {path}")

def fix_position_manager():
    path = "core/position_manager.py"
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
    
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Fix the missing except/finally block error and indentation
    # Specifically looking for the broken try blocks I introduced
    
    # 1. Fix the CB status try block
    old_cb_block = """                    try:
                        from utils.effective_config import get_effective_value
                        if get_effective_value('trading_circuit_breaker_enabled') or get_effective_value('trading_circuit_breaker_enabled') is None:
                            from core.trading_circuit_breaker import get_trading_circuit_breaker
                            trading_cb = get_trading_circuit_breaker()
                            cb_status = trading_cb.get_status()
                            trade_data['entry_cb_state'] = cb_status.get('state', 'ACTIVE')
                            trade_data['entry_consecutive_losses'] = cb_status.get('consecutive_losses', 0)
                            trade_data['entry_daily_pnl_pct'] = cb_status.get('daily_pnl_pct', 0)
                            trade_data['entry_cb_score_boost'] = cb_status.get('score_boost', 0)
                        else:
                            trade_data['entry_cb_state'] = 'DISABLED'
                            trade_data['entry_consecutive_losses'] = 0
                            trade_data['entry_daily_pnl_pct'] = 0
                            trade_data['entry_cb_score_boost'] = 0
                    except Exception as e:
                        logger.debug(f"⚠️ Impossible de récupérer CB: {e}")"""
    
    # Actually, I'll just rewrite the whole method or block carefully
    # Looking at the previous read_file output for line 4082 area
    
    # 2. Fix the Phase 2D feedback loop
    # ... existing code ...
    
    # Let's do a simpler approach: replace with correct versions
    
    # Fix for line 2844 (missing pass)
    content = content.replace("                except Exception:\n\n", "                except Exception:\n                    pass\n\n")
    
    # Fix the CB block (around 4082)
    # The previous attempt had some weird nesting or missing lines
    
    # I will use a more robust way to fix the indentation issues
    lines = content.splitlines()
    fixed_lines = []
    for line in lines:
        fixed_line = line.replace('\t', '    ') # Replace tabs with 4 spaces
        fixed_lines.append(fixed_line)
    
    content = '\n'.join(fixed_lines) + '\n'
    
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print(f"Normalized indentation in {path}")

if __name__ == "__main__":
    fix_analyzer()
    fix_position_manager()
