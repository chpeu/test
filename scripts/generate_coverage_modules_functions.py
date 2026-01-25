import ast
import os
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class FunctionSpan:
    qualname: str
    start: int
    end: int


class FunctionCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self._class_stack: List[str] = []
        self._func_stack: List[str] = []
        self.functions: List[FunctionSpan] = []

    def visit_ClassDef(self, node: ast.ClassDef):
        self._class_stack.append(node.name)
        self.generic_visit(node)
        self._class_stack.pop()

    def _push_func(self, name: str) -> None:
        self._func_stack.append(name)

    def _pop_func(self) -> None:
        self._func_stack.pop()

    def _qualname(self, func_name: str) -> str:
        parts = []
        if self._class_stack:
            parts.extend(self._class_stack)
        if self._func_stack:
            parts.extend(self._func_stack)
        parts.append(func_name)
        return ".".join(parts)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_function(node)

    def _handle_function(self, node: ast.AST):
        func_name = getattr(node, "name", "<lambda>")
        qualname = self._qualname(func_name)
        start = getattr(node, "lineno", None)
        end = getattr(node, "end_lineno", None)
        if start is not None and end is not None and end >= start:
            self.functions.append(FunctionSpan(qualname=qualname, start=int(start), end=int(end)))

        # support nested functions
        self._push_func(func_name)
        self.generic_visit(node)
        self._pop_func()


def parse_coverage_xml(path: str) -> Dict[str, Dict[int, int]]:
    """Return mapping: filename -> {line_number -> hits}."""
    root = ET.parse(path).getroot()
    out: Dict[str, Dict[int, int]] = {}

    for cls in root.findall(".//class"):
        filename = cls.get("filename")
        if not filename:
            continue

        lines: Dict[int, int] = out.setdefault(filename, {})
        for ln in cls.findall("./lines/line"):
            number = ln.get("number")
            hits = ln.get("hits")
            if not number:
                continue
            try:
                n = int(number)
            except ValueError:
                continue
            try:
                h = int(hits) if hits is not None else 0
            except ValueError:
                h = 0
            lines[n] = h

    return out


def coverage_for_span(line_hits: Dict[int, int], start: int, end: int) -> Tuple[int, int, float]:
    """Return (covered, total, pct) for executable lines within [start, end]."""
    total = 0
    covered = 0
    for ln, hits in line_hits.items():
        if start <= ln <= end:
            total += 1
            if hits > 0:
                covered += 1
    pct = (covered / total * 100.0) if total else 100.0
    return covered, total, pct


def safe_read_text(path: str) -> Optional[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except UnicodeDecodeError:
        try:
            with open(path, "r", encoding="latin-1") as f:
                return f.read()
        except Exception:
            return None
    except Exception:
        return None


def main() -> int:
    repo_root = os.getcwd()
    coverage_path = os.path.join(repo_root, "coverage.xml")

    if not os.path.exists(coverage_path):
        print(f"ERROR: coverage.xml not found at {coverage_path}")
        return 2

    cov = parse_coverage_xml(coverage_path)

    # Build per-file coverage summary
    file_summaries: List[Tuple[str, int, int, float]] = []
    per_file_functions: Dict[str, List[Tuple[str, int, int, float]]] = {}

    for filename, line_hits in sorted(cov.items()):
        # ignore non-python
        if not filename.endswith(".py"):
            continue

        # ignore coverage internals
        if filename.startswith("htmlcov"):
            continue

        abs_path = os.path.join(repo_root, filename)
        if not os.path.exists(abs_path):
            # Some entries may be generated/absent; still include file-level if possible
            covered, total, pct = coverage_for_span(line_hits, 1, 10**9)
            file_summaries.append((filename, covered, total, pct))
            per_file_functions[filename] = []
            continue

        src = safe_read_text(abs_path)
        if src is None:
            covered, total, pct = coverage_for_span(line_hits, 1, 10**9)
            file_summaries.append((filename, covered, total, pct))
            per_file_functions[filename] = []
            continue

        try:
            tree = ast.parse(src, filename=filename)
        except SyntaxError:
            covered, total, pct = coverage_for_span(line_hits, 1, 10**9)
            file_summaries.append((filename, covered, total, pct))
            per_file_functions[filename] = []
            continue

        collector = FunctionCollector()
        collector.visit(tree)

        fn_rows: List[Tuple[str, int, int, float]] = []
        for fn in collector.functions:
            c, t, p = coverage_for_span(line_hits, fn.start, fn.end)
            fn_rows.append((fn.qualname, c, t, p))

        # file total
        covered, total, pct = coverage_for_span(line_hits, 1, 10**9)
        file_summaries.append((filename, covered, total, pct))

        # sort functions by start line by re-parsing mapping (qualname only has no start), keep stable
        # We'll sort by pct ascending then name for easy spotting.
        fn_rows.sort(key=lambda r: (r[3], r[0]))
        per_file_functions[filename] = fn_rows

    # Sort files by pct ascending (worst first)
    file_summaries.sort(key=lambda r: (r[3], r[0]))

    out_path = os.path.join(repo_root, "COVERAGE_MODULES_FUNCTIONS.md")
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("# Coverage Report (Modules / Functions)\n\n")
        f.write(f"Generated from `coverage.xml` on `{now}`.\n\n")
        f.write(f"Total python modules in coverage: **{len([x for x in cov.keys() if x.endswith('.py')])}**\n\n")

        f.write("## Modules summary (worst coverage first)\n\n")
        f.write("| Module | Lines Covered | Lines Total | Coverage |\n")
        f.write("|---|---:|---:|---:|\n")
        for filename, covered, total, pct in file_summaries:
            f.write(f"| `{filename}` | {covered} | {total} | {pct:.2f}% |\n")

        f.write("\n## Functions by module\n\n")
        for filename, covered, total, pct in file_summaries:
            f.write(f"### `{filename}` ({pct:.2f}% - {covered}/{total})\n\n")
            fn_rows = per_file_functions.get(filename, [])
            if not fn_rows:
                f.write("(No functions detected or source unavailable.)\n\n")
                continue

            f.write("| Function | Lines Covered | Lines Total | Coverage |\n")
            f.write("|---|---:|---:|---:|\n")
            for qualname, c, t, p in fn_rows:
                f.write(f"| `{qualname}` | {c} | {t} | {p:.2f}% |\n")
            f.write("\n")

    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
