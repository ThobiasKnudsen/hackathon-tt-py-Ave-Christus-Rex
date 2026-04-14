"""
Import rewriter for translated TypeScript code.

Replaces emitter-generated import paths (literal TS module translations)
with correct Python imports for the wrapper framework and runtime helpers.
"""
from __future__ import annotations

import re

# Standard library imports to prepend
_STDLIB_HEADER = """\
from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timedelta
import copy
import sys
"""

# Import lines to strip entirely (already handled by emitter or stdlib)
_STRIP_PATTERNS = [
    r"from big\.js import",
    r"from lodash import",
    r"from ghostfolio\.common\.interfaces import",
    r"from ghostfolio\.common\.models import",
    r"from ghostfolio\.common\.types import",
    r"from ghostfolio\.common\.types\.",
]

# Import replacements: (pattern, replacement)
_REPLACE_RULES = [
    # Base class
    (
        r"from ghostfolio\.api\.app\.portfolio\.calculator\.portfolio_calculator import.*",
        "from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator",
    ),
    # Portfolio helper → runtime_helpers
    (
        r"from ghostfolio\.api\.helper\.portfolio\.helper import.*",
        "from .runtime_helpers import get_factor",
    ),
    # Common helper → runtime_helpers
    (
        r"from ghostfolio\.common\.helper import.*",
        "from .runtime_helpers import DATE_FORMAT",
    ),
    # Common calculation helper
    (
        r"from ghostfolio\.common\.calculation_helper import.*",
        "from .runtime_helpers import get_interval_from_date_range",
    ),
    # NestJS Logger → runtime_helpers
    (
        r"from nestjs\.common import.*",
        "from .runtime_helpers import Logger",
    ),
    # date-fns → runtime_helpers
    (
        r"from date_fns import.*",
        "from .runtime_helpers import (\n"
        "    add_milliseconds, difference_in_days, each_year_of_interval,\n"
        "    format_date, is_before, is_this_year, parse_date, JSObj,\n"
        ")",
    ),
    # Portfolio order item interface → strip
    (
        r"from ghostfolio\.api\.app\.portfolio\.interfaces\..* import.*",
        "",
    ),
]


def rewrite_imports(source: str) -> str:
    """Rewrite emitter-generated imports to work with the wrapper framework."""
    lines = source.split("\n")
    import_lines = []
    body_lines = []
    imports_done = False

    for line in lines:
        stripped = line.strip()

        # Skip empty lines in the import section
        if not stripped and not imports_done:
            continue

        # Check if this is an import line
        if not imports_done and (stripped.startswith("from ") or stripped.startswith("import ")):
            # Check strip patterns
            if any(re.match(pat, stripped) for pat in _STRIP_PATTERNS):
                continue

            # Check replacement rules
            replaced = False
            for pattern, replacement in _REPLACE_RULES:
                if re.match(pattern, stripped):
                    if replacement:
                        import_lines.append(replacement)
                    replaced = True
                    break

            if not replaced:
                import_lines.append(line)
            continue

        # First non-import, non-empty line ends the import section
        if not imports_done and stripped:
            imports_done = True

        body_lines.append(line)

    # Deduplicate imports
    seen = set()
    unique_imports = []
    for imp in import_lines:
        if imp not in seen:
            seen.add(imp)
            unique_imports.append(imp)

    return _STDLIB_HEADER + "\n" + "\n".join(unique_imports) + "\n\n" + "\n".join(body_lines)
