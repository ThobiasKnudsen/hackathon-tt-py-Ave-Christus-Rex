"""
TypeScript to Python translator.

Orchestrates the pipeline: parse (tree-sitter) → emit (AST walk) → write.
"""
from __future__ import annotations

import sys
from pathlib import Path

from .ts_parser import parse_file, parse_typescript
from .emitter import Emitter, EmitResult


def translate_source(ts_content: str, *, debug: bool = False) -> EmitResult:
    """Translate TypeScript source string to Python."""
    result = parse_typescript(ts_content)
    if result.has_errors:
        errs = result.errors
        for e in errs[:5]:
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

    Args:
        ts_path: Path to the TypeScript source file.
        output_path: Where to write the Python output. None = don't write.
        debug: Enable debug annotations and logging.
        dry_run: Parse and emit but don't write to disk.

    Returns:
        EmitResult with the translated source and diagnostics.
    """
    result = parse_file(ts_path)
    if result.has_errors:
        errs = result.errors
        print(f"Parse errors in {ts_path}:", file=sys.stderr)
        for e in errs[:5]:
            print(f"  L{e.start_line}: {e.text[:60]}", file=sys.stderr)

    emitter = Emitter(debug=debug, source_bytes=result.source)
    emit_result = emitter.emit(result.root)

    if debug or dry_run:
        emit_result.print_warnings()

    if not dry_run and output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(emit_result.source, encoding="utf-8")
        print(f"  {ts_path.name} → {output_path}")

    return emit_result


def translate_directory(
    ts_dir: Path,
    output_dir: Path,
    *,
    debug: bool = False,
    dry_run: bool = False,
    pattern: str = "*.ts",
) -> list[EmitResult]:
    """Translate all TypeScript files in a directory."""
    results = []
    ts_files = sorted(ts_dir.rglob(pattern))

    # Skip test/spec files
    ts_files = [f for f in ts_files if ".spec." not in f.name and ".test." not in f.name]

    for ts_file in ts_files:
        rel = ts_file.relative_to(ts_dir)
        out_file = output_dir / rel.with_suffix(".py")
        result = translate_file(ts_file, out_file, debug=debug, dry_run=dry_run)
        results.append(result)

    return results


def run_translation(repo_root: Path, output_dir: Path, *, debug: bool = False,
                    dry_run: bool = False) -> None:
    """Run the translation process for the hackathon target."""
    # Source TypeScript file
    ts_source = (
        repo_root / "projects" / "ghostfolio" / "apps" / "api" / "src"
        / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
    )

    # Stub file from the example (base to compare against)
    stub_source = (
        repo_root / "translations" / "ghostfolio_pytx_example" / "app"
        / "implementation" / "portfolio" / "calculator" / "roai"
        / "portfolio_calculator.py"
    )

    # Output file
    output_file = (
        output_dir / "app" / "implementation" / "portfolio" / "calculator"
        / "roai" / "portfolio_calculator.py"
    )

    if not ts_source.exists():
        print(f"Warning: TypeScript source not found: {ts_source}", file=sys.stderr)
        return

    print(f"Translating {ts_source.name}...")
    result = translate_file(ts_source, output_file, debug=debug, dry_run=dry_run)

    if dry_run:
        print("\n--- Dry run output ---")
        print(result.source)
        print("--- End dry run ---")
    else:
        print(f"  → {output_file}")

    # Summary
    n_warn = len(result.warnings)
    n_unhandled = len(result.unhandled_types)
    print(f"  Warnings: {n_warn}, Unhandled types: {n_unhandled}")
    if result.unhandled_types:
        print(f"  Unhandled: {sorted(result.unhandled_types)}")
