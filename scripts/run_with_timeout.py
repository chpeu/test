import argparse
import os
import subprocess
import sys
from typing import List, Optional


def _kill_process_tree_windows(pid: int) -> None:
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    except Exception:
        return


def _run(cmd: List[str], timeout_s: Optional[float], cwd: Optional[str]) -> int:
    if not cmd:
        raise ValueError("cmd vide")

    popen_kwargs = {
        "cwd": cwd,
    }

    if os.name == "nt":
        popen_kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    proc = subprocess.Popen(cmd, **popen_kwargs)

    try:
        if timeout_s is None or timeout_s <= 0:
            return proc.wait()
        return proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        print(f"TIMEOUT after {timeout_s}s -> killing pid={proc.pid}", file=sys.stderr)
        if os.name == "nt":
            _kill_process_tree_windows(proc.pid)
        else:
            try:
                proc.kill()
            except Exception:
                pass
        return 124


def main() -> int:
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("--timeout", type=float, default=60.0)
    ap.add_argument("--cwd", default=None)
    ap.add_argument("cmd", nargs=argparse.REMAINDER)
    args = ap.parse_args()

    cmd = list(args.cmd)
    if cmd and cmd[0] == "--":
        cmd = cmd[1:]

    if not cmd:
        print(
            "Usage: python scripts/run_with_timeout.py --timeout 20 -- <command> [args...]\n"
            "Example: python scripts/run_with_timeout.py --timeout 20 -- python scripts/analyze_last_42_trades.py",
            file=sys.stderr,
        )
        return 2

    return _run(cmd=cmd, timeout_s=float(args.timeout), cwd=args.cwd)


if __name__ == "__main__":
    raise SystemExit(main())
