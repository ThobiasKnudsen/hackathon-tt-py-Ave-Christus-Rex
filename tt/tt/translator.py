"""
TypeScript to Python translator.

Orchestrates the pipeline: parse → emit → rewrite imports → write.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from .ts_parser import parse_file, parse_typescript
from .emitter import Emitter, EmitResult
from .import_rewriter import rewrite_imports

_SCAFFOLD_DIR = Path(__file__).parent / "scaffold" / "ghostfolio_pytx"


def translate_source(ts_content: str, *, debug: bool = False) -> EmitResult:
    """Translate TypeScript source string to Python."""
    result = parse_typescript(ts_content)
    if result.has_errors:
        for e in result.errors[:5]:
            print(f"  Parse error at L{e.start_line}: {e.text[:60]}", file=sys.stderr)

    emitter = Emitter(debug=debug, source_bytes=result.source)
    return emitter.emit(result.root)


def translate_file(
    ts_path: Path,
    output_path: Path | None = None,
    *,
    debug: bool = False,
    dry_run: bool = False,
) -> EmitResult:
    """Translate a TypeScript file to Python.

    Returns:
        EmitResult with the translated source and diagnostics.
    """
    result = parse_file(ts_path)
    if result.has_errors:
        print(f"Parse errors in {ts_path}:", file=sys.stderr)
        for e in result.errors[:5]:
            print(f"  L{e.start_line}: {e.text[:60]}", file=sys.stderr)

    emitter = Emitter(debug=debug, source_bytes=result.source)
    emit_result = emitter.emit(result.root)

    # Rewrite imports for the wrapper framework
    emit_result.source = rewrite_imports(emit_result.source)

    # Inject adapter methods from scaffold template
    emit_result.source = _inject_adapter_methods(emit_result.source)

    if debug or dry_run:
        emit_result.print_warnings()

    if not dry_run and output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(emit_result.source, encoding="utf-8")
        print(f"  {ts_path.name} → {output_path}")

    return emit_result


def _inject_adapter_methods(source: str) -> str:
    """Inject adapter methods from scaffold template into the class body."""
    adapter_file = (
        _SCAFFOLD_DIR / "app" / "implementation" / "portfolio"
        / "calculator" / "roai" / "adapter_methods.py"
    )
    if not adapter_file.exists():
        return source

    text = adapter_file.read_text(encoding="utf-8")
    # Extract between markers
    start_marker = "# --- begin adapter methods ---"
    end_marker = "# --- end adapter methods ---"
    start_idx = text.find(start_marker)
    end_idx = text.find(end_marker)
    if start_idx < 0 or end_idx < 0:
        return source
    # Keep leading whitespace intact — only strip trailing
    adapter_body = text[start_idx + len(start_marker):end_idx]
    # Remove only the first empty line (from the newline after the marker)
    if adapter_body.startswith("\n"):
        adapter_body = adapter_body[1:]
    adapter_body = adapter_body.rstrip()

    # Append adapter methods to end of class (before final newline)
    # Find the last non-empty line
    lines = source.rstrip().split("\n")
    return "\n".join(lines) + "\n\n" + adapter_body + "\n"


def _deploy_runtime_helpers(output_dir: Path) -> None:
    """Copy runtime_helpers.py from scaffold to the output implementation dir."""
    helpers_src = (
        _SCAFFOLD_DIR / "app" / "implementation" / "portfolio"
        / "calculator" / "roai" / "runtime_helpers.py"
    )
    helpers_dst = (
        output_dir / "app" / "implementation" / "portfolio"
        / "calculator" / "roai" / "runtime_helpers.py"
    )

    if helpers_src.exists():
        helpers_dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(helpers_src, helpers_dst)
        print(f"  Deployed runtime_helpers.py")
    else:
        print(f"  Warning: runtime_helpers.py not found at {helpers_src}",
              file=sys.stderr)


def run_translation(repo_root: Path, output_dir: Path, *, debug: bool = False,
                    dry_run: bool = False) -> None:
    """Run the translation process for the hackathon target."""
    ts_source = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
    )

    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )

    if not ts_source.exists():
        print(f"Warning: TypeScript source not found: {ts_source}", file=sys.stderr)
        return

    # Deploy runtime helpers to output directory
    if not dry_run:
        _deploy_runtime_helpers(output_dir)

    print(f"Translating {ts_source.name}...")
    result = translate_file(ts_source, output_file, debug=debug, dry_run=dry_run)

    if dry_run:
        print("\n--- Dry run output ---")
        print(result.source)
        print("--- End dry run ---")

    # Summary
    n_warn = len(result.warnings)
    n_unhandled = len(result.unhandled_types)
    print(f"  Warnings: {n_warn}, Unhandled types: {n_unhandled}")
    if result.unhandled_types:
        print(f"  Unhandled: {sorted(result.unhandled_types)}")
