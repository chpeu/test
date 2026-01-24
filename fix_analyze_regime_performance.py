from pathlib import Path


def main() -> None:
    path = Path(__file__).with_name('analyze_regime_performance.py')
    text = path.read_text(encoding='utf-8', errors='replace')
    lines = text.splitlines()

    try:
        idx_sqlite = next(i for i, l in enumerate(lines) if l.strip() == 'import sqlite3')
    except StopIteration as e:
        raise SystemExit("ERROR: could not find 'import sqlite3'") from e

    new_head = [
        'import os',
        'import sys',
        'import io',
        '',
        "if os.environ.get('PYTEST_CURRENT_TEST') is not None or __name__ != '__main__':",
        "    raise ImportError('analyze_regime_performance is a script-only module')",
        '',
        'try:',
        "    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')",
        'except Exception:',
        '    pass',
        '',
    ]

    out = new_head + lines[idx_sqlite:]

    try:
        tail_idx = next(i for i, l in enumerate(out) if "print('📝 PROCHAINES ÉTAPES:')" in l)
    except StopIteration:
        tail_idx = len(out)

    fixed: list[str] = []
    skip_next = False

    for i, l in enumerate(out):
        if i >= tail_idx:
            s = l.strip()

            if s == "print('=' * 120)":
                fixed.append("print('=' * 120)")
                continue

            if s == 'conn.close()':
                fixed.append('conn.close()')
                continue

            if s == "if __name__ == '__main__':":
                skip_next = True
                continue

            if skip_next and s == 'main()':
                skip_next = False
                continue

            skip_next = False

        fixed.append(l)

    path.write_text('\n'.join(fixed).rstrip() + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
