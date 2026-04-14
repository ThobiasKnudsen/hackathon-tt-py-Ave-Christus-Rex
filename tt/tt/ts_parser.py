"""
Tree-sitter based TypeScript parser.

Provides robust parsing of TypeScript files into syntax trees with
debugging and inspection utilities.
"""
from __future__ import annotations

import sys
from pathlib import Path
from dataclasses import dataclass, field

import tree_sitter_typescript as tsts
from tree_sitter import Language, Parser, Node

TS_LANGUAGE = Language(tsts.language_typescript())


def create_parser() -> Parser:
    """Create a configured TypeScript parser."""
    return Parser(TS_LANGUAGE)


# ---------------------------------------------------------------------------
# Thin wrapper around tree-sitter Node for debugging convenience
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NodeInfo:
    """Lightweight snapshot of a tree-sitter Node for inspection."""
    type: str
    text: str
    start_line: int          # 1-indexed
    end_line: int            # 1-indexed
    start_col: int
    end_col: int
    field_name: str | None   # field name in parent (e.g. "name", "body")
    child_count: int
    is_named: bool
    has_error: bool

    @classmethod
    def from_node(cls, node: Node, field_name: str | None = None) -> NodeInfo:
        return cls(
            type=node.type,
            text=node.text.decode("utf-8", errors="replace"),
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            start_col=node.start_point[1],
            end_col=node.end_point[1],
            field_name=field_name,
            child_count=node.child_count,
            is_named=node.is_named,
            has_error=node.has_error,
        )


# ---------------------------------------------------------------------------
# Parse result
# ---------------------------------------------------------------------------

@dataclass
class ParseResult:
    """Result of parsing a TypeScript file."""
    tree: object           # tree_sitter.Tree
    root: Node
    source: bytes
    path: Path | None

    @property
    def has_errors(self) -> bool:
        return self.root.has_error

    @property
    def errors(self) -> list[NodeInfo]:
        """Collect all ERROR nodes in the tree."""
        result = []
        _collect_errors(self.root, result)
        return result

    def source_for(self, node: Node) -> str:
        """Get the original source text for a node."""
        return self.source[node.start_byte:node.end_byte].decode(
            "utf-8", errors="replace"
        )

    def line(self, lineno: int) -> str:
        """Get a 1-indexed source line."""
        lines = self.source.decode("utf-8", errors="replace").splitlines()
        if 1 <= lineno <= len(lines):
            return lines[lineno - 1]
        return ""


def _collect_errors(node: Node, acc: list[NodeInfo]) -> None:
    if node.type == "ERROR":
        acc.append(NodeInfo.from_node(node))
    for child in node.children:
        _collect_errors(child, acc)


# ---------------------------------------------------------------------------
# Core parse function
# ---------------------------------------------------------------------------

_parser_instance: Parser | None = None


def _get_parser() -> Parser:
    global _parser_instance
    if _parser_instance is None:
        _parser_instance = create_parser()
    return _parser_instance


def parse_typescript(source: str | bytes, path: Path | None = None) -> ParseResult:
    """Parse TypeScript source code and return a ParseResult.

    Args:
        source: TypeScript source code (str or bytes).
        path: Optional file path (for error messages).
    """
    if isinstance(source, str):
        source = source.encode("utf-8")
    parser = _get_parser()
    tree = parser.parse(source)
    return ParseResult(tree=tree, root=tree.root_node, source=source, path=path)


def parse_file(path: str | Path) -> ParseResult:
    """Parse a TypeScript file from disk."""
    p = Path(path)
    source = p.read_bytes()
    parser = _get_parser()
    tree = parser.parse(source)
    return ParseResult(tree=tree, root=tree.root_node, source=source, path=p)


# ---------------------------------------------------------------------------
# Tree navigation helpers
# ---------------------------------------------------------------------------

def find_nodes(root: Node, node_type: str) -> list[Node]:
    """Find all descendant nodes matching a given type."""
    results: list[Node] = []
    _find_nodes_recursive(root, node_type, results)
    return results


def _find_nodes_recursive(node: Node, node_type: str, acc: list[Node]) -> None:
    if node.type == node_type:
        acc.append(node)
    for child in node.children:
        _find_nodes_recursive(child, node_type, acc)


def find_first(root: Node, node_type: str) -> Node | None:
    """Find the first descendant node of the given type."""
    if root.type == node_type:
        return root
    for child in root.children:
        result = find_first(child, node_type)
        if result is not None:
            return result
    return None


def named_children(node: Node) -> list[Node]:
    """Return only named (non-punctuation) children of a node."""
    return [c for c in node.children if c.is_named]


def child_by_type(node: Node, type_name: str) -> Node | None:
    """Find the first direct child with the given type."""
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def children_by_type(node: Node, type_name: str) -> list[Node]:
    """Find all direct children with the given type."""
    return [c for c in node.children if c.type == type_name]


def node_text(node: Node) -> str:
    """Get the text content of a node."""
    return node.text.decode("utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Debug printing
# ---------------------------------------------------------------------------

def dump_tree(
    node: Node,
    *,
    indent: int = 0,
    max_depth: int | None = None,
    show_text: bool = True,
    show_unnamed: bool = True,
    file=None,
) -> None:
    """Pretty-print a syntax tree for debugging.

    Args:
        node: Root node to print from.
        indent: Current indentation level.
        max_depth: Stop descending after this many levels (None = unlimited).
        show_text: Show text content for leaf nodes.
        show_unnamed: Include unnamed nodes (punctuation like {, }, ;).
        file: Output stream (defaults to stderr).
    """
    if file is None:
        file = sys.stderr

    if max_depth is not None and indent > max_depth:
        return

    if not show_unnamed and not node.is_named:
        return

    prefix = "  " * indent
    loc = f"L{node.start_point[0]+1}:{node.start_point[1]}"
    span = f"{node.start_point[0]+1}-{node.end_point[0]+1}"

    # Field name in parent
    field_label = ""
    if node.parent:
        for i, child in enumerate(node.parent.children):
            if child.id == node.id:
                fname = node.parent.field_name_for_child(i)
                if fname:
                    field_label = f"{fname}: "
                break

    # Leaf text
    text = ""
    if show_text and node.child_count == 0:
        raw = node.text.decode("utf-8", errors="replace")
        if len(raw) <= 60:
            text = f" = {raw!r}"
        else:
            text = f" = {raw[:57]!r}..."

    # Error highlight
    err = " *** ERROR ***" if node.type == "ERROR" else ""

    print(f"{prefix}{field_label}{node.type} [{span}]{text}{err}", file=file)

    for child in node.children:
        dump_tree(
            child,
            indent=indent + 1,
            max_depth=max_depth,
            show_text=show_text,
            show_unnamed=show_unnamed,
            file=file,
        )


def dump_node(node: Node, *, file=None) -> None:
    """Print a single node's details (not its children)."""
    if file is None:
        file = sys.stderr

    info = NodeInfo.from_node(node)
    print(f"Type:       {info.type}", file=file)
    print(f"Lines:      {info.start_line}-{info.end_line}", file=file)
    print(f"Named:      {info.is_named}", file=file)
    print(f"Children:   {info.child_count}", file=file)
    print(f"Has error:  {info.has_error}", file=file)

    # Show named children
    nc = named_children(node)
    if nc:
        print("Named children:", file=file)
        for c in nc:
            ct = c.text.decode("utf-8", errors="replace")
            preview = ct[:60].replace("\n", "\\n") if len(ct) <= 60 else ct[:57].replace("\n", "\\n") + "..."
            print(f"  {c.type}: {preview!r}", file=file)

    # Show fields
    fields_seen = set()
    for i, c in enumerate(node.children):
        fname = node.field_name_for_child(i)
        if fname and fname not in fields_seen:
            fields_seen.add(fname)
            ct = c.text.decode("utf-8", errors="replace")
            preview = ct[:60].replace("\n", "\\n") if len(ct) <= 60 else ct[:57].replace("\n", "\\n") + "..."
            print(f"  field '{fname}' -> {c.type}: {preview!r}", file=file)

    # Source preview
    raw = node.text.decode("utf-8", errors="replace")
    if len(raw) > 200:
        raw = raw[:200] + "..."
    print(f"Text:\n{raw}", file=file)


def _get_member_name(member: Node) -> str:
    """Extract the property_identifier name from a class member node."""
    for mc in member.children:
        if mc.type == "property_identifier":
            return node_text(mc)
    return ""


def _summarize_class(cls_node: Node, file) -> None:
    """Print summary of a class declaration's members."""
    name_node = cls_node.child_by_field_name("name")
    name = node_text(name_node) if name_node else "?"
    print(f"  export class {name}  [L{cls_node.start_point[0]+1}-{cls_node.end_point[0]+1}]", file=file)

    body = cls_node.child_by_field_name("body")
    if not body:
        return
    for member in body.children:
        mname = _get_member_name(member)
        if member.type == "method_definition":
            lines = member.end_point[0] - member.start_point[0] + 1
            print(f"    method {mname}()  [{lines} lines, L{member.start_point[0]+1}-{member.end_point[0]+1}]", file=file)
        elif member.type == "public_field_definition":
            print(f"    field {mname}  [L{member.start_point[0]+1}]", file=file)


def _summarize_child(child: Node, file) -> None:
    """Print summary line for a single top-level statement."""
    if child.type == "import_statement":
        src_node = child.child_by_field_name("source")
        src = node_text(src_node) if src_node else "?"
        print(f"  import from {src}  [L{child.start_point[0]+1}]", file=file)
    elif child.type == "export_statement":
        for ic in named_children(child):
            if ic.type == "class_declaration":
                _summarize_class(ic, file)
            else:
                print(f"  export {ic.type}  [L{ic.start_point[0]+1}]", file=file)
    else:
        preview = node_text(child)[:60].replace("\n", "\\n")
        print(f"  {child.type}: {preview}  [L{child.start_point[0]+1}]", file=file)


def summary(result: ParseResult, *, file=None) -> None:
    """Print a structural summary of a parsed file."""
    if file is None:
        file = sys.stderr

    path_str = str(result.path) if result.path else "<string>"
    print(f"=== Parse Summary: {path_str} ===", file=file)
    print(f"Errors: {len(result.errors)}", file=file)

    for err in result.errors:
        preview = err.text[:80].replace("\n", "\\n")
        print(f"  ERROR at line {err.start_line}: {preview}", file=file)

    print(f"\nTop-level statements ({result.root.child_count} total):", file=file)
    for child in result.root.children:
        if child.is_named:
            _summarize_child(child, file)

    print("=" * 50, file=file)
