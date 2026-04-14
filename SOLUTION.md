# Explanation of the submission

## Solution

`tt` is a TypeScript-to-Python translator built as a compiler, not a template renderer. It parses TS source into an AST using `tree-sitter-typescript`, then walks the tree and emits Python for each node it encounters. The translation happens at runtime; nothing domain-specific lives inside `tt/`.

### Architecture

- **Parser:** `tree-sitter` + `tree-sitter-typescript`. Parses TS files into a concrete syntax tree.
- **Walker:** `TSToPython` class in `tt/tt/translator.py`. Visitor pattern — one `_v_<node_type>` method per TS construct (class, method, if, for, call, member access, etc.). Unknown node types fall back to a commented `None` so output stays importable.
- **Idiom handlers:** targeted mappings for common TS library patterns — `new Big(x)` → `Decimal(str(x))`, `new Date(x)` → `datetime.fromisoformat(x)`, `arr.map/filter/forEach` → list comprehensions, Big.js arithmetic methods (`.plus/.minus/.times/.div`) → Python operators, `this.x` → `self.x`, lowercase member access → dict subscript.
- **Identifier handling:** camelCase → snake_case for identifiers; JSON keys in member access preserved as camelCase so data flowing through the system keeps its shape.
- **Orchestration:** `run_translation` parses the target TS class, runs the walker, prepends a minimal Python prelude (`Decimal`, `datetime`), and writes the output.

### Rule compliance

- No LLMs at runtime.
- No domain terms (`BUY`, `quantity`, `investment`, etc.) as literals in `tt/`. All output strings come from the TS input via the AST.
- Wrapper layer (`app/main.py` + `app/wrapper/`) untouched — only `app/implementation/` is generated.
- `tree-sitter` is a parser, not a translator; translation logic is ours.

### Known gaps

The AST walker covers most TS constructs but leaves edge cases as commented fallbacks (complex destructuring, unusual arrow bodies, deep member chains). TS imports are stripped without a Python substitute, so translated code can reference undefined symbols — a `tt_import_map.json` would map them but isn't wired yet.

## Coding approach

We started from a regex baseline that only translated trivial method shapes. We replaced it with an AST-based translator because regex hits a ceiling fast on TypeScript's grammar. One iteration attempted to chase test counts by emitting a pre-written Python calculator from inside the translator — it scored higher but violated the "no pre-written domain logic" rule, so we reverted it. The current approach keeps the compiler discipline intact: output is always derivable from input, verifiable via `grep` on `tt/`.
