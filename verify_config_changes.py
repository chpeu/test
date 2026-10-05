import sys
import json


def _setup_stdout_utf8() -> None:
    try:
        if sys.platform == 'win32' and sys.stdout is sys.__stdout__ and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


def main() -> None:
    _setup_stdout_utf8()

    with open('config_overrides.json', 'r') as f:
        data = json.load(f)

    print('=' * 80)
    print('VERIFICATION DES PARAMETRES MODIFIES')
    print('=' * 80)

    changes = [
        ('gb_min_confidence', 0.47, 0.55),
        ('atr_mult_sl', 1.5, 2.0),
        ('atr_mult_tp', 1.5, 2.0),
        ('ml_calibration_enabled', False, True),
        ('ml_calib_min_winrate', 45.0, 50.0),
        ('trailing_enabled', False, True),
    ]

    all_ok = True
    for param, old_val, new_val in changes:
        current_val = data.get(param)
        status = '✅' if current_val == new_val else '❌'
        print(f'{status} {param}:')
        print(f'   Avant: {old_val}')
        print(f'   Attendu: {new_val}')
        print(f'   Actuel: {current_val}')
        if current_val != new_val:
            all_ok = False
        print()

    print('=' * 80)
    if all_ok:
        print('✅ TOUS LES PARAMETRES SONT CORRECTS')
    else:
        print('❌ CERTAINS PARAMETRES NE SONT PAS CORRECTS')
    print('=' * 80)


if __name__ == '__main__':
    main()
