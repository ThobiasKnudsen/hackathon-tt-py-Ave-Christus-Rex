"""
Tree-sitter AST to Python emitter.

Walks a TypeScript tree-sitter AST and emits equivalent Python source code.
Uses a visitor-dispatch pattern: each node type maps to a handler function.

Designed for debuggability:
- Every unhandled node type produces a visible comment in output
- Optional debug mode tags each line with the TS source line
- Accumulated warnings and emit log for post-mortem inspection
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Callable

from tree_sitter import Node

from .ts_parser import node_text, named_children, child_by_type, children_by_type

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Name conversion helpers
# ---------------------------------------------------------------------------

_CAMEL_RE_1 = re.compile(r"(.)([A-Z][a-z]+)")
_CAMEL_RE_2 = re.compile(r"([a-z0-9])([A-Z])")


def to_snake_case(name: str) -> str:
    """Convert camelCase or PascalCase to snake_case."""
    s = _CAMEL_RE_1.sub(r"\1_\2", name)
    return _CAMEL_RE_2.sub(r"\1_\2", s).lower()


def _is_class_name(name: str) -> bool:
    """Heuristic: PascalCase names are class names, keep as-is."""
    return bool(name) and name[0].isupper() and not name.isupper()


def convert_name(name: str) -> str:
    """Convert a TS identifier to Python convention."""
    if _is_class_name(name):
        return name  # keep PascalCase for classes
    if name.isupper() or "_" in name:
        return name  # already UPPER_CASE or snake_case
    return to_snake_case(name)


# ---------------------------------------------------------------------------
# Known function/method mappings (generic, not domain-specific)
# ---------------------------------------------------------------------------

# Big.js methods that map to binary operators
_BIG_OPERATOR_MAP = {
    "plus": "+",
    "minus": "-",
    "mul": "*",
    "div": "/",
    "add": "+",
}

# Big.js methods that map to comparison operators
_BIG_COMPARISON_MAP = {
    "eq": "==",
    "gt": ">",
    "lt": "<",
    "gte": ">=",
    "lte": "<=",
}

# TS binary operators → Python
_BINOP_MAP = {
    "===": "==",
    "!==": "!=",
    "&&": "and",
    "||": "or",
    # "??" handled specially in _emit_binary_expression
    "instanceof": "isinstance",  # handled specially
}

# Known TS global/utility functions → Python equivalents
_FUNC_MAP = {
    "console.log": "print",
    "console.warn": "print",
    "console.error": "print",
    "Math.abs": "abs",
    "Math.max": "max",
    "Math.min": "min",
    "Math.floor": "int",
    "Math.ceil": "math.ceil",
    "Math.round": "round",
    "Object.keys": "list",  # Object.keys(x) → list(x.keys())
    "Object.values": "list",
    "Object.entries": "list",
    "Array.isArray": "isinstance",
    "JSON.stringify": "json.dumps",
    "JSON.parse": "json.loads",
    "Number.EPSILON": "sys.float_info.epsilon",
}


# ---------------------------------------------------------------------------
# Emit result
# ---------------------------------------------------------------------------

@dataclass
class EmitLogEntry:
    """Single entry in the emit log for debugging."""
    node_type: str
    ts_line: int
    py_output: str


@dataclass
class EmitResult:
    """Result of emitting a full file."""
    source: str
    warnings: list[str] = field(default_factory=list)
    emit_log: list[EmitLogEntry] = field(default_factory=list)
    unhandled_types: set[str] = field(default_factory=set)

    def print_warnings(self) -> None:
        if not self.warnings:
            return
        print(f"\n--- Emit warnings ({len(self.warnings)}) ---")
        for w in self.warnings:
            print(f"  {w}")
        if self.unhandled_types:
            print(f"  Unhandled node types: {sorted(self.unhandled_types)}")


# ---------------------------------------------------------------------------
# Emitter
# ---------------------------------------------------------------------------

class Emitter:
    """Walks a tree-sitter TypeScript AST and emits Python source."""

    def __init__(self, *, debug: bool = False, source_bytes: bytes | None = None):
        self.debug = debug
        self.source_bytes = source_bytes
        self._indent = 0
        self._warnings: list[str] = []
        self._emit_log: list[EmitLogEntry] = []
        self._unhandled: set[str] = set()
        # Rename context: maps original TS identifier names → replacement strings.
        # Used when inlining arrow function bodies into comprehensions.
        self._rename_ctx: dict[str, str] = {}
        # Pre-statements: helper functions that need to be emitted before
        # the current statement (e.g. sort key helpers).
        self._pre_stmts: list[str] = []

        # Build dispatch table
        self._dispatch: dict[str, Callable[[Node], str]] = {}
        for attr in dir(self):
            if attr.startswith("_emit_"):
                node_type = attr[6:]
                self._dispatch[node_type] = getattr(self, attr)

    # -- public API --

    def emit(self, root: Node) -> EmitResult:
        """Emit Python source from a tree-sitter root node."""
        output = self._node(root)
        return EmitResult(
            source=output,
            warnings=list(self._warnings),
            emit_log=list(self._emit_log),
            unhandled_types=set(self._unhandled),
        )

    # -- core dispatch --

    def _node(self, node: Node) -> str:
        """Dispatch a single node to its handler."""
        handler = self._dispatch.get(node.type)
        if handler is not None:
            result = handler(node)
            self._log(node, result)
            return result

        # Unnamed nodes (punctuation, operators) → return text directly
        if not node.is_named:
            return node_text(node)

        # Fallback for unhandled named nodes
        self._unhandled.add(node.type)
        ts_line = node.start_point[0] + 1
        text = node_text(node)
        preview = text[:60].replace("\n", "\\n")
        self._warn(f"Unhandled node type '{node.type}' at L{ts_line}: {preview}")
        return f"# UNHANDLED: {node.type} at L{ts_line}: {preview}"

    def _children_text(self, node: Node, *, sep: str = "", skip_comments: bool = False) -> str:
        """Emit all named children joined by sep."""
        children = named_children(node)
        if skip_comments:
            children = [c for c in children if c.type != "comment"]
        return sep.join(self._node(c) for c in children)

    def _all_children_text(self, node: Node, *, sep: str = "") -> str:
        """Emit all children (including unnamed) joined by sep."""
        return sep.join(self._node(c) for c in node.children)

    # -- indentation --

    def _indent_str(self) -> str:
        return "    " * self._indent

    def _indented(self, text: str) -> str:
        """Prefix non-empty text with current indentation."""
        lines = []
        for line in text.split("\n"):
            if line.strip():
                lines.append(self._indent_str() + line)
            else:
                lines.append("")
        return "\n".join(lines)

    def _line(self, text: str, node: Node | None = None) -> str:
        """Create an indented line, optionally with debug source ref."""
        result = self._indent_str() + text
        if self.debug and node is not None:
            ts_line = node.start_point[0] + 1
            result += f"  # L{ts_line}"
        return result

    # -- logging / warnings --

    def _warn(self, msg: str) -> None:
        self._warnings.append(msg)
        log.warning("emitter: %s", msg)

    def _log(self, node: Node, output: str) -> None:
        if self.debug:
            self._emit_log.append(EmitLogEntry(
                node_type=node.type,
                ts_line=node.start_point[0] + 1,
                py_output=output[:120],
            ))

    # -- helpers --

    def _get_text(self, node: Node) -> str:
        """Get raw text of a node."""
        return node_text(node)

    def _field(self, node: Node, name: str) -> Node | None:
        """Get a field child by name."""
        return node.child_by_field_name(name)

    def _field_text(self, node: Node, name: str) -> str:
        """Get text of a field child."""
        child = self._field(node, name)
        return node_text(child) if child else ""

    # -- JS truthiness --

    _SIMPLE_COND_TYPES = frozenset({
        "identifier", "member_expression", "subscript_expression",
        "call_expression",
    })

    def _is_simple_condition(self, node: Node | None) -> bool:
        """True if node is a simple expression that needs js_truthy wrapping.

        Binary expressions (==, &&, ||), unary ! and boolean literals already
        produce correct Python truthiness and don't need wrapping.
        """
        if node is None:
            return False
        # Unwrap parenthesized_expression
        if node.type == "parenthesized_expression":
            inner = named_children(node)
            return self._is_simple_condition(inner[0]) if inner else False
        return node.type in self._SIMPLE_COND_TYPES

    def _wrap_condition(self, cond_str: str, cond_node: Node | None) -> str:
        """Wrap a condition string with js_truthy() if the node is simple."""
        if self._is_simple_condition(cond_node):
            return f"js_truthy({cond_str})"
        return cond_str

    # ======================================================================
    # Node handlers — one per tree-sitter node type
    # ======================================================================

    def _emit_program(self, node: Node) -> str:
        parts = []
        for child in node.children:
            if not child.is_named:
                continue
            parts.append(self._node(child))
        return "\n\n".join(parts) + "\n"

    # -- imports --

    def _emit_import_statement(self, node: Node) -> str:
        source_node = node.child_by_field_name("source")
        if source_node is None:
            return self._line(f"# import: {self._get_text(node)}", node)

        module_path = self._get_text(source_node).strip("'\"")

        # Extract imported names
        clause = child_by_type(node, "import_clause")
        names = []
        if clause:
            for imp in children_by_type(clause, "named_imports"):
                for spec in children_by_type(imp, "import_specifier"):
                    name_node = spec.child_by_field_name("name")
                    alias_node = spec.child_by_field_name("alias")
                    if name_node:
                        name = self._get_text(name_node)
                        if alias_node:
                            alias = self._get_text(alias_node)
                            names.append(f"{name} as {alias}")
                        else:
                            names.append(name)
            # Default import
            ident = child_by_type(clause, "identifier")
            if ident:
                names.append(self._get_text(ident))

        # Convert module path to Python-style
        py_module = module_path.replace("@", "").replace("/", ".").replace("-", "_")
        # Strip leading dots
        py_module = py_module.lstrip(".")

        if names:
            names_str = ", ".join(names)
            return self._line(f"from {py_module} import {names_str}", node)
        return self._line(f"import {py_module}", node)

    # -- exports --

    def _emit_export_statement(self, node: Node) -> str:
        # export class Foo → just emit the class
        inner = named_children(node)
        parts = []
        for child in inner:
            if child.type in ("type_annotation", "type_identifier"):
                continue
            parts.append(self._node(child))
        return "\n".join(parts)

    # -- classes --

    def _emit_class_declaration(self, node: Node) -> str:
        name_node = self._field(node, "name")
        name = self._get_text(name_node) if name_node else "UnknownClass"

        # Heritage (extends)
        bases = []
        heritage = child_by_type(node, "class_heritage")
        if heritage:
            extends = child_by_type(heritage, "extends_clause")
            if extends:
                for c in named_children(extends):
                    if c.type == "identifier" or c.type == "type_identifier":
                        bases.append(self._get_text(c))

        bases_str = f"({', '.join(bases)})" if bases else ""
        header = self._line(f"class {name}{bases_str}:", node)

        body = self._field(node, "body")
        if body:
            self._indent += 1
            body_str = self._emit_class_body(body)
            self._indent -= 1
            return f"{header}\n{body_str}"
        return f"{header}\n{self._indent_str()}    pass"

    def _emit_class_body(self, node: Node) -> str:
        members = []
        for child in node.children:
            if not child.is_named:
                continue
            members.append(self._node(child))
        if not members:
            return self._line("pass")
        return "\n\n".join(members)

    def _emit_class_heritage(self, node: Node) -> str:
        # Handled inside class_declaration
        return ""

    def _emit_extends_clause(self, node: Node) -> str:
        return ""

    # -- methods and fields --

    def _emit_method_definition(self, node: Node) -> str:
        # Extract access modifier, name, params, return type, body
        name = ""
        params_node = None
        body_node = None
        is_static = False

        for child in node.children:
            if child.type == "accessibility_modifier":
                continue  # skip public/private/protected
            elif child.type == "property_identifier":
                name = self._get_text(child)
            elif child.type == "formal_parameters":
                params_node = child
            elif child.type == "statement_block":
                body_node = child
            elif child.type == "type_annotation":
                continue
            elif not child.is_named and self._get_text(child) == "static":
                is_static = True

        py_name = convert_name(name)
        params = self._emit_params(params_node, is_method=True, is_static=is_static)

        header = self._line(f"def {py_name}({params}):", node)

        if body_node:
            self._indent += 1
            body_str = self._emit_statement_block_inner(body_node)
            self._indent -= 1
            if not body_str.strip():
                body_str = self._indent_str() + "    pass"
            return f"{header}\n{body_str}"
        return f"{header}\n{self._indent_str()}    pass"

    def _emit_accessibility_modifier(self, node: Node) -> str:
        return ""  # strip access modifiers

    def _emit_public_field_definition(self, node: Node) -> str:
        name_node = None
        value_node = None
        for child in node.children:
            if child.type == "property_identifier":
                name_node = child
            elif child.type == "type_annotation":
                continue
            elif child.type in ("accessibility_modifier",):
                continue
            elif name_node and value_node is None and child.is_named:
                value_node = child

        if name_node is None:
            return self._line("# field: could not parse", node)

        py_name = convert_name(self._get_text(name_node))

        if value_node:
            val = self._node(value_node)
            return self._line(f"{py_name} = {val}", node)
        return self._line(f"{py_name} = None", node)

    # -- parameters --

    def _emit_params(self, node: Node | None, *, is_method: bool = False,
                     is_static: bool = False) -> str:
        params = []
        if is_method and not is_static:
            params.append("self")

        if node is None:
            return ", ".join(params)

        for child in named_children(node):
            if child.type == "required_parameter":
                p = self._emit_required_parameter(child)
                params.append(p)
            elif child.type == "optional_parameter":
                p = self._emit_optional_parameter(child)
                params.append(p)
            elif child.type == "object_pattern":
                # Destructured params → individual params
                for prop in named_children(child):
                    if prop.type == "shorthand_property_identifier_pattern":
                        params.append(convert_name(self._get_text(prop)))
                    elif prop.type == "pair_pattern" or prop.type == "pair":
                        key = self._field(prop, "key")
                        if key:
                            params.append(convert_name(self._get_text(key)))

        return ", ".join(params)

    def _emit_required_parameter(self, node: Node) -> str:
        name_node = node.child_by_field_name("pattern") or child_by_type(node, "identifier")
        if name_node is None:
            obj_pat = child_by_type(node, "object_pattern")
            if obj_pat:
                return self._extract_object_pattern_params(obj_pat)
            return "arg"
        # Handle destructured parameter: ({ a, b, c }: Type) → a, b, c
        if name_node.type == "object_pattern":
            return self._extract_object_pattern_params(name_node)
        name = convert_name(self._get_text(name_node))
        return name

    def _extract_object_pattern_params(self, obj_pat: Node) -> str:
        """Extract comma-separated parameter names from an object pattern."""
        names = []
        for prop in named_children(obj_pat):
            if prop.type == "shorthand_property_identifier_pattern":
                names.append(convert_name(self._get_text(prop)))
            elif prop.type in ("pair_pattern", "pair"):
                key = self._field(prop, "key")
                if key:
                    names.append(convert_name(self._get_text(key)))
        return ", ".join(names) if names else "_"

    def _emit_optional_parameter(self, node: Node) -> str:
        name_node = node.child_by_field_name("pattern") or child_by_type(node, "identifier")
        name = convert_name(self._get_text(name_node)) if name_node else "arg"

        # Default value
        value_node = node.child_by_field_name("value")
        if value_node:
            val = self._node(value_node)
            return f"{name}={val}"
        return f"{name}=None"

    def _emit_formal_parameters(self, node: Node) -> str:
        return self._emit_params(node)

    # -- statements --

    def _emit_statement_block(self, node: Node) -> str:
        self._indent += 1
        result = self._emit_statement_block_inner(node)
        self._indent -= 1
        return result

    def _emit_statement_block_inner(self, node: Node) -> str:
        """Emit the contents of a statement block (without changing indent)."""
        stmts = []
        for child in node.children:
            if not child.is_named:
                continue
            s = self._node(child)
            if s.strip():
                stmts.append(s)
        if not stmts:
            return self._line("pass")
        return "\n".join(stmts)

    def _flush_pre_stmts(self) -> str:
        """Drain and return any accumulated pre-statements."""
        if not self._pre_stmts:
            return ""
        result = "\n".join(self._pre_stmts)
        self._pre_stmts.clear()
        return result + "\n"

    def _emit_expression_statement(self, node: Node) -> str:
        inner = named_children(node)
        if not inner:
            return ""
        expr = self._node(inner[0])
        pre = self._flush_pre_stmts()
        # If it's already indented (from a nested emit), return as-is
        if expr.startswith(self._indent_str()):
            return pre + expr
        return pre + self._line(expr, node)

    def _emit_lexical_declaration(self, node: Node) -> str:
        # let x = ... or const x = ...
        parts = []
        for child in named_children(node):
            if child.type == "variable_declarator":
                parts.append(self._emit_variable_declarator(child))
        pre = self._flush_pre_stmts()
        return pre + "\n".join(parts)

    def _emit_variable_declarator(self, node: Node) -> str:
        name_node = self._field(node, "name")
        value_node = self._field(node, "value")

        if name_node is None:
            return self._line("# variable: could not parse name", node)

        # Handle destructuring
        if name_node.type == "object_pattern":
            return self._emit_object_destructure(name_node, value_node, node)
        elif name_node.type == "array_pattern":
            return self._emit_array_destructure(name_node, value_node, node)

        name = convert_name(self._get_text(name_node))

        # Type annotation on the name
        type_ann = child_by_type(node, "type_annotation")

        if value_node:
            val = self._node(value_node)
            return self._line(f"{name} = {val}", node)
        return self._line(f"{name} = None", node)

    def _emit_object_destructure(self, name_node: Node, value_node: Node | None,
                                 ctx_node: Node) -> str:
        """const { a, b } = expr → a = expr['a']; b = expr['b']"""
        if value_node is None:
            return self._line("# destructure: no value", ctx_node)

        val = self._node(value_node)
        lines = []
        tmp = f"_tmp_{ctx_node.start_point[0]}"
        lines.append(self._line(f"{tmp} = {val}", ctx_node))

        for prop in named_children(name_node):
            if prop.type == "shorthand_property_identifier_pattern":
                key = self._get_text(prop)
                py_key = convert_name(key)
                lines.append(self._line(f"{py_key} = {tmp}[\"{key}\"]"))
            elif prop.type == "pair_pattern" or prop.type == "pair":
                key_node = self._field(prop, "key")
                val_pat = self._field(prop, "value")
                if key_node:
                    key = self._get_text(key_node)
                    py_var = convert_name(self._get_text(val_pat)) if val_pat else convert_name(key)
                    lines.append(self._line(f"{py_var} = {tmp}[\"{key}\"]"))

        return "\n".join(lines)

    def _emit_array_destructure(self, name_node: Node, value_node: Node | None,
                                ctx_node: Node) -> str:
        if value_node is None:
            return self._line("# array destructure: no value", ctx_node)

        val = self._node(value_node)
        names = []
        for child in named_children(name_node):
            names.append(convert_name(self._get_text(child)))

        if names:
            return self._line(f"{', '.join(names)} = {val}", ctx_node)
        return self._line(f"_ = {val}", ctx_node)

    def _emit_return_statement(self, node: Node) -> str:
        inner = named_children(node)
        if not inner:
            return self._line("return", node)
        val = self._node(inner[0])
        return self._line(f"return {val}", node)

    def _emit_if_statement(self, node: Node) -> str:
        cond_node = self._field(node, "condition")
        cons_node = self._field(node, "consequence")
        alt_node = self._field(node, "alternative")

        cond = self._node(cond_node) if cond_node else "True"
        # Strip outer parens if present
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1]
        # Unwrap parenthesized_expression for the node check
        inner_cond = cond_node
        if inner_cond and inner_cond.type == "parenthesized_expression":
            nc = named_children(inner_cond)
            if nc:
                inner_cond = nc[0]
        cond = self._wrap_condition(cond, inner_cond)

        header = self._line(f"if {cond}:", node)

        parts = [header]
        if cons_node:
            self._indent += 1
            body = self._emit_statement_block_inner(cons_node)
            self._indent -= 1
            parts.append(body)
        else:
            parts.append(self._indent_str() + "    pass")

        if alt_node:
            parts.append(self._node(alt_node))

        return "\n".join(parts)

    def _emit_else_clause(self, node: Node) -> str:
        inner = named_children(node)
        if not inner:
            return self._line("else:") + "\n" + self._indent_str() + "    pass"

        child = inner[0]
        if child.type == "if_statement":
            return self._emit_elif(child, node)

        # Plain else
        return self._emit_plain_else(child, node)

    def _emit_elif(self, if_node: Node, else_node: Node) -> str:
        """Emit else if → elif."""
        cond_node = self._field(if_node, "condition")
        cons_node = self._field(if_node, "consequence")
        alt_node = self._field(if_node, "alternative")

        cond = self._node(cond_node) if cond_node else "True"
        if cond.startswith("(") and cond.endswith(")"):
            cond = cond[1:-1]
        inner_cond = cond_node
        if inner_cond and inner_cond.type == "parenthesized_expression":
            nc = named_children(inner_cond)
            if nc:
                inner_cond = nc[0]
        cond = self._wrap_condition(cond, inner_cond)

        parts = [self._line(f"elif {cond}:", else_node)]
        if cons_node:
            self._indent += 1
            parts.append(self._emit_statement_block_inner(cons_node))
            self._indent -= 1
        if alt_node:
            parts.append(self._node(alt_node))
        return "\n".join(parts)

    def _emit_plain_else(self, child: Node, node: Node) -> str:
        """Emit a plain else clause."""
        header = self._line("else:", node)
        if child.type == "statement_block":
            self._indent += 1
            body = self._emit_statement_block_inner(child)
            self._indent -= 1
            return f"{header}\n{body}"
        self._indent += 1
        body = self._node(child)
        self._indent -= 1
        return f"{header}\n{body}"

    def _emit_for_statement(self, node: Node) -> str:
        # C-style for loop: for (init; cond; update) { body }
        init_node = self._field(node, "initializer")
        cond_node = self._field(node, "condition")
        update_node = self._field(node, "increment")
        body_node = self._field(node, "body")

        # Emit as while loop
        parts = []
        if init_node:
            init = self._node(init_node)
            parts.append(init)

        cond = self._node(cond_node) if cond_node else "True"
        parts.append(self._line(f"while {cond}:", node))

        if body_node:
            self._indent += 1
            if update_node:
                upd_text = self._node(update_node)
                # Check for 'continue' in the body to decide wrapping
                # Emit body at +1 indent (inside try block) if wrapping
                raw_body = self._emit_statement_block_inner(body_node)
                if "continue" in raw_body:
                    # Re-emit body at one deeper indent for try block
                    self._indent += 1
                    body_inner = self._emit_statement_block_inner(body_node)
                    self._indent -= 1
                    body = self._line("try:") + "\n"
                    body += body_inner + "\n"
                    body += self._line("finally:") + "\n"
                    self._indent += 1
                    body += self._line(upd_text)
                    self._indent -= 1
                else:
                    body = raw_body
                    body += "\n" + self._line(upd_text, update_node)
            else:
                body = self._emit_statement_block_inner(body_node)
            self._indent -= 1
            parts.append(body)
        else:
            self._indent += 1
            if update_node:
                parts.append(self._line(self._node(update_node)))
            else:
                parts.append(self._line("pass"))
            self._indent -= 1

        return "\n".join(parts)

    def _emit_for_in_statement(self, node: Node) -> str:
        # for (const x of arr) or for (const x in obj)
        left_node = self._field(node, "left")
        right_node = self._field(node, "right")
        body_node = self._field(node, "body")

        left = self._node(left_node).strip() if left_node else "_"
        # Remove let/const prefix
        for prefix in ("let ", "const ", "var "):
            if left.startswith(prefix):
                left = left[len(prefix):]

        right = self._node(right_node) if right_node else "[]"
        header = self._line(f"for {left} in {right}:", node)

        parts = [header]
        if body_node:
            self._indent += 1
            body = self._emit_statement_block_inner(body_node)
            self._indent -= 1
            parts.append(body)
        else:
            parts.append(self._indent_str() + "    pass")

        return "\n".join(parts)

    def _emit_break_statement(self, node: Node) -> str:
        return self._line("break", node)

    def _emit_continue_statement(self, node: Node) -> str:
        return self._line("continue", node)

    # -- expressions --

    def _emit_assignment_expression(self, node: Node) -> str:
        left_node = self._field(node, "left")
        right_node = self._field(node, "right")
        left = self._node(left_node) if left_node else "?"
        right = self._node(right_node) if right_node else "None"
        return f"{left} = {right}"

    def _emit_augmented_assignment_expression(self, node: Node) -> str:
        left_node = self._field(node, "left")
        right_node = self._field(node, "right")
        op_node = self._field(node, "operator")
        left = self._node(left_node) if left_node else "?"
        right = self._node(right_node) if right_node else "0"
        op = self._get_text(op_node) if op_node else "+="
        return f"{left} {op} {right}"

    def _emit_update_expression(self, node: Node) -> str:
        # i++ → i += 1, i-- → i -= 1
        text = self._get_text(node)
        for child in node.children:
            if child.is_named:
                var = self._node(child)
                if "++" in text:
                    return f"{var} += 1"
                elif "--" in text:
                    return f"{var} -= 1"
        return f"# update: {text}"

    def _emit_call_expression(self, node: Node) -> str:
        func_node = self._field(node, "function")
        args_node = self._field(node, "arguments")

        if func_node is None:
            return "# call: could not parse"

        # Dispatch to method call handler for obj.method() patterns
        if func_node.type == "member_expression":
            result = self._try_method_call(func_node, args_node, node)
            if result is not None:
                return result

        # Try known global/utility function mappings
        result = self._try_global_call(func_node, args_node, node)
        if result is not None:
            return result

        # Generic call
        func = self._node(func_node)
        args = self._emit_args_list(args_node)
        return f"{func}({', '.join(args)})"

    def _try_method_call(self, func_node: Node, args_node: Node | None,
                         call_node: Node) -> str | None:
        """Handle obj.method() calls. Returns None if not a known pattern."""
        obj_node = self._field(func_node, "object")
        prop_node = self._field(func_node, "property")
        if prop_node is None:
            return None

        method = self._get_text(prop_node)

        # Big.js arithmetic: .plus() .minus() .mul() .div() .add()
        if method in _BIG_OPERATOR_MAP:
            obj = self._node(obj_node) if obj_node else "?"
            args = self._emit_args_list(args_node)
            return f"({obj} {_BIG_OPERATOR_MAP[method]} {args[0]})" if args else obj

        # Big.js comparisons: .eq() .gt() .lt() .gte() .lte()
        if method in _BIG_COMPARISON_MAP:
            obj = self._node(obj_node) if obj_node else "?"
            args = self._emit_args_list(args_node)
            return f"({obj} {_BIG_COMPARISON_MAP[method]} {args[0]})" if args else obj

        return self._try_method_call_misc(obj_node, args_node, method)

    # Methods that delegate to higher-order comprehension handlers
    _COMPREHENSION_METHODS = {
        "filter": "_emit_filter_call",
        "map": "_emit_map_call",
        "find": "_emit_find_call",
        "findIndex": "_emit_find_index_call",
        "forEach": "_emit_foreach_call",
    }

    def _try_method_call_misc(self, obj_node: Node | None, args_node: Node | None,
                              method: str) -> str | None:
        """Handle miscellaneous method calls (toFixed, filter, push, etc.)."""
        if method == "toFixed":
            return self._emit_to_fixed(obj_node, args_node)
        if method == "toNumber":
            return f"float({self._node(obj_node) if obj_node else '?'})"
        if method == "sort":
            return f"sorted({self._node(obj_node) if obj_node else '?'})"

        # Higher-order array methods
        handler_name = self._COMPREHENSION_METHODS.get(method)
        if handler_name:
            return getattr(self, handler_name)(obj_node, args_node)

        return self._try_method_call_simple(obj_node, args_node, method)

    def _emit_to_fixed(self, obj_node: Node | None, args_node: Node | None) -> str:
        obj = self._node(obj_node) if obj_node else "?"
        args = self._emit_args_list(args_node)
        return f"round(float({obj}), {args[0]})" if args else f"float({obj})"

    def _try_method_call_simple(self, obj_node: Node | None, args_node: Node | None,
                                method: str) -> str | None:
        """Handle simple method translations (includes, push, at, getTime)."""
        obj = self._node(obj_node) if obj_node else "?"
        args = self._emit_args_list(args_node)

        if method == "includes":
            return f"({args[0]} in {obj})" if args else "(True)"
        if method == "push":
            return f"{obj}.append({', '.join(args)})"
        if method == "at":
            return f"{obj}[{args[0]}]" if args else None
        # Date methods
        if method == "getTime":
            return f"{obj}.timestamp()"
        if method == "getFullYear":
            return f"{obj}.year"
        if method == "getMonth":
            return f"({obj}.month - 1)"  # JS months are 0-indexed
        if method == "getDate":
            return f"{obj}.day"
        return None

    def _try_global_call(self, func_node: Node, args_node: Node | None,
                         call_node: Node) -> str | None:
        """Handle known global/utility function calls. Returns None if unknown."""
        func_text = self._get_text(func_node)

        if func_text in _FUNC_MAP:
            args = self._emit_args_list(args_node)
            return f"{_FUNC_MAP[func_text]}({', '.join(args)})"

        if func_text == "sortBy":
            return self._emit_sort_by(args_node, call_node)

        return self._try_global_call_misc(func_text, args_node)

    def _try_global_call_misc(self, func_text: str,
                              args_node: Node | None) -> str | None:
        """Handle miscellaneous global calls (cloneDeep, format, etc.)."""
        if func_text == "cloneDeep":
            args = self._emit_args_list(args_node)
            return f"copy.deepcopy({', '.join(args)})"

        if func_text == "format":
            args = self._emit_args_list(args_node)
            if len(args) >= 2:
                return f"format_date({args[0]}, {args[1]})"
            return f"format_date({args[0]})" if args else "str(None)"

        if func_text == "isBefore":
            args = self._emit_args_list(args_node)
            return f"({args[0]} < {args[1]})" if len(args) >= 2 else "False"

        if func_text == "differenceInDays":
            args = self._emit_args_list(args_node)
            return f"({args[0]} - {args[1]}).days" if len(args) >= 2 else "0"

        if func_text == "addMilliseconds":
            args = self._emit_args_list(args_node)
            if len(args) >= 2:
                return f"({args[0]} + timedelta(milliseconds={args[1]}))"
            return args[0] if args else "None"

        if func_text == "isThisYear":
            args = self._emit_args_list(args_node)
            return f"({args[0]}.year == datetime.now().year)" if args else "False"

        if func_text == "eachYearOfInterval":
            args = self._emit_args_list(args_node)
            return f"each_year_of_interval({', '.join(args)})" if args else "[]"

        if func_text == "getIntervalFromDateRange":
            args = self._emit_args_list(args_node)
            return f"get_interval_from_date_range({', '.join(args)})"

        return None

    def _emit_sort_by(self, args_node: Node | None, call_node: Node) -> str:
        """Handle sortBy(arr, fn) from lodash."""
        arr_nodes = list(named_children(args_node)) if args_node else []
        arrow = arr_nodes[1] if len(arr_nodes) >= 2 and arr_nodes[1].type == "arrow_function" else None

        if arrow:
            param_names, is_destr, body_expr, body_node = self._extract_arrow_info(arrow)
            arr_str = self._node(arr_nodes[0])

            if body_expr is not None:
                cond = self._emit_arrow_body_with_rename(body_expr, param_names, is_destr, "_x")
                return f"sorted({arr_str}, key=lambda _x: {cond})"

            if body_node:
                return self._emit_sort_by_helper(arr_str, param_names, is_destr, body_node, call_node)

        args = self._emit_args_list(args_node)
        if len(args) >= 2:
            return f"sorted({args[0]}, key={args[1]})"
        return f"sorted({args[0]})" if args else "sorted([])"

    def _emit_sort_by_helper(self, arr_str: str, param_names: list[str],
                             is_destr: bool, body_node: Node, call_node: Node) -> str:
        """Emit a helper function for multi-statement sortBy arrow."""
        helper_name = f"_sort_key_{call_node.start_point[0]}"
        header = self._line(f"def {helper_name}(_item):")
        self._indent += 1
        unpack_lines = []
        if is_destr:
            for n in param_names:
                unpack_lines.append(self._line(f'{convert_name(n)} = _item["{n}"]'))
        old_ctx = dict(self._rename_ctx)
        if is_destr:
            for n in param_names:
                self._rename_ctx[n] = convert_name(n)
        body_str = self._emit_statement_block_inner(body_node)
        self._rename_ctx = old_ctx
        self._indent -= 1
        helper = header + "\n" + "\n".join(unpack_lines) + ("\n" if unpack_lines else "") + body_str
        self._pre_stmts.append(helper)
        return f"sorted({arr_str}, key={helper_name})"

    def _emit_args_list(self, node: Node | None) -> list[str]:
        """Emit arguments as a list of strings."""
        if node is None:
            return []
        result = []
        for child in named_children(node):
            if child.type == "comment":
                continue  # skip comments inside argument lists
            result.append(self._node(child))
        return result

    def _emit_arguments(self, node: Node) -> str:
        args = self._emit_args_list(node)
        return f"({', '.join(args)})"

    def _emit_new_expression(self, node: Node) -> str:
        constructor = self._field(node, "constructor")
        args_node = self._field(node, "arguments")
        if constructor is None:
            return "None"

        class_name = self._get_text(constructor)
        args = self._emit_args_list(args_node)

        # new Big(x) → Decimal(str(x))
        if class_name == "Big":
            if args:
                return f"Decimal(str({args[0]}))"
            return "Decimal('0')"

        # new Date(x) → datetime(x) or datetime.fromisoformat(x)
        if class_name == "Date":
            if not args:
                return "datetime.now()"
            if len(args) == 1:
                return f"datetime.fromisoformat({args[0]})"
            return f"datetime({', '.join(args)})"

        # Generic constructor
        return f"{class_name}({', '.join(args)})"

    # Known static member → Python equivalents
    _STATIC_MEMBER_MAP = {
        "Number.EPSILON": "sys.float_info.epsilon",
        "Number.MAX_SAFE_INTEGER": "sys.maxsize",
        "Number.MIN_SAFE_INTEGER": "-sys.maxsize",
        "Number.MAX_VALUE": "float('inf')",
        "Number.MIN_VALUE": "sys.float_info.min",
        "Number.NaN": "float('nan')",
        "Number.POSITIVE_INFINITY": "float('inf')",
        "Number.NEGATIVE_INFINITY": "float('-inf')",
        "Math.PI": "math.pi",
        "Math.E": "math.e",
        # PortfolioCalculator statics → self reference (base class is immutable)
        "PortfolioCalculator.ENABLE_LOGGING": "self.ENABLE_LOGGING",
    }

    def _emit_member_expression(self, node: Node) -> str:
        obj_node = self._field(node, "object")
        prop_node = self._field(node, "property")

        obj_text = self._get_text(obj_node) if obj_node else "?"
        prop = self._get_text(prop_node) if prop_node else "?"

        # Check static member mappings (Number.EPSILON, Math.PI, etc.)
        full = f"{obj_text}.{prop}"
        if full in self._STATIC_MEMBER_MAP:
            return self._STATIC_MEMBER_MAP[full]

        obj = self._node(obj_node) if obj_node else "?"

        # .length → len(obj or []) to handle None (JS returns undefined.length = undefined)
        if prop == "length":
            return f"len({obj} or [])"

        # Handle optional chaining (already separate node type, but just in case)
        optional = child_by_type(node, "optional_chain")
        py_prop = convert_name(prop)

        if optional:
            return f"getattr({obj}, '{py_prop}', None)"

        return f"{obj}.{py_prop}"

    def _emit_optional_chain(self, node: Node) -> str:
        return ""  # handled in member_expression

    def _emit_subscript_expression(self, node: Node) -> str:
        obj_node = self._field(node, "object")
        index_node = self._field(node, "index")
        obj = self._node(obj_node) if obj_node else "?"
        index = self._node(index_node) if index_node else "?"

        # Check for optional chaining ?.[
        has_optional = False
        for child in node.children:
            if not child.is_named and self._get_text(child) == "?.":
                has_optional = True

        if has_optional:
            return f"({obj} or {{}}).get({index})"

        return f"{obj}[{index}]"

    def _emit_binary_expression(self, node: Node) -> str:
        left_node = self._field(node, "left")
        right_node = self._field(node, "right")
        op_node = self._field(node, "operator")

        left = self._node(left_node) if left_node else "?"
        right = self._node(right_node) if right_node else "?"
        op = self._get_text(op_node) if op_node else "?"

        # ?? (nullish coalescing) → safe fallback
        # NOT `or` — Decimal(0) is falsy in Python but truthy in JS
        if op == "??":
            # obj[key] ?? default → obj.get(key, default)
            if left_node and left_node.type == "subscript_expression":
                obj_n = self._field(left_node, "object")
                idx_n = self._field(left_node, "index")
                obj_s = self._node(obj_n) if obj_n else "?"
                idx_s = self._node(idx_n) if idx_n else "?"
                return f"{obj_s}.get({idx_s}, {right})"
            # obj?.prop ?? default → getattr(obj, 'prop', default)
            return f"({left} if {left} is not None else {right})"

        # instanceof → isinstance(left, right)
        if op == "instanceof":
            # Big → Decimal
            cls = "Decimal" if right == "Big" else right
            return f"isinstance({left}, {cls})"

        # Map TS operators to Python
        py_op = _BINOP_MAP.get(op, op)
        return f"({left} {py_op} {right})"

    def _emit_unary_expression(self, node: Node) -> str:
        text = self._get_text(node)
        op = ""
        operand = None
        for child in node.children:
            if not child.is_named:
                op = self._get_text(child)
            else:
                operand = child

        if operand is None:
            return text

        val = self._node(operand)

        if op == "!":
            if self._is_simple_condition(operand):
                return f"not js_truthy({val})"
            return f"not {val}"
        if op == "typeof":
            return f"type({val}).__name__"
        return f"{op}{val}"

    def _emit_ternary_expression(self, node: Node) -> str:
        cond_node = self._field(node, "condition")
        cons_node = self._field(node, "consequence")
        alt_node = self._field(node, "alternative")

        cond = self._node(cond_node) if cond_node else "True"
        cond = self._wrap_condition(cond, cond_node)
        cons = self._node(cons_node) if cons_node else "None"
        alt = self._node(alt_node) if alt_node else "None"

        return f"({cons} if {cond} else {alt})"

    def _emit_parenthesized_expression(self, node: Node) -> str:
        inner = named_children(node)
        if inner:
            return f"({self._node(inner[0])})"
        return "()"

    def _extract_arrow_info(self, node: Node):
        """Extract (param_names, is_destructured, body_expr, body_node)
        from an arrow function. body_expr is the single return expression if available."""
        params_node = self._field(node, "parameters") or self._field(node, "parameter")
        body_node = self._field(node, "body")

        param_names, is_destructured = self._extract_arrow_params(params_node)
        body_expr = self._extract_arrow_body_expr(body_node)

        return param_names, is_destructured, body_expr, body_node

    def _extract_arrow_params(self, params_node: Node | None) -> tuple[list[str], bool]:
        """Extract parameter names and destructuring flag from arrow params."""
        if params_node is None:
            return [], False
        if params_node.type == "identifier":
            return [self._get_text(params_node)], False

        names: list[str] = []
        is_destr = False
        if params_node.type == "formal_parameters":
            for child in named_children(params_node):
                if child.type == "identifier":
                    names.append(self._get_text(child))
                elif child.type == "required_parameter":
                    n, d = self._extract_param_pattern(child)
                    names.extend(n)
                    is_destr = is_destr or d
                elif child.type == "object_pattern":
                    is_destr = True
                    names.extend(self._extract_obj_pattern_names(child))
        return names, is_destr

    def _extract_param_pattern(self, param: Node) -> tuple[list[str], bool]:
        """Extract names from a required_parameter node."""
        pat = param.child_by_field_name("pattern") or child_by_type(param, "identifier")
        if pat and pat.type == "object_pattern":
            return self._extract_obj_pattern_names(pat), True
        if pat:
            return [self._get_text(pat)], False
        return [], False

    def _extract_obj_pattern_names(self, obj_pat: Node) -> list[str]:
        """Extract property names from an object_pattern."""
        names = []
        for prop in named_children(obj_pat):
            if prop.type == "shorthand_property_identifier_pattern":
                names.append(self._get_text(prop))
            elif prop.type in ("pair_pattern", "pair"):
                key = self._field(prop, "key")
                if key:
                    names.append(self._get_text(key))
        return names

    def _extract_arrow_body_expr(self, body_node: Node | None) -> Node | None:
        """Extract single return expression from arrow body, or None."""
        if body_node is None:
            return None
        if body_node.type != "statement_block":
            return body_node
        stmts = [c for c in body_node.children if c.is_named]
        if len(stmts) == 1 and stmts[0].type == "return_statement":
            ret_inner = named_children(stmts[0])
            if ret_inner:
                return ret_inner[0]
        return None

    def _emit_arrow_body_with_rename(self, node: Node, param_names: list[str],
                                     is_destructured: bool, item_var: str) -> str:
        """Emit an arrow body expression, substituting destructured params
        with item_var['name'] access or renaming simple param to item_var."""
        old_ctx = dict(self._rename_ctx)
        try:
            if is_destructured:
                for name in param_names:
                    self._rename_ctx[name] = f'{item_var}["{name}"]'
            elif len(param_names) == 1:
                self._rename_ctx[param_names[0]] = item_var
            return self._node(node)
        finally:
            self._rename_ctx = old_ctx

    def _emit_arrow_function(self, node: Node) -> str:
        param_names, is_destructured, body_expr, body_node = self._extract_arrow_info(node)

        if is_destructured:
            # Destructured arrow → lambda _x: body with _x["prop"] access
            if body_expr is not None:
                body = self._emit_arrow_body_with_rename(body_expr, param_names, True, "_x")
                return f"lambda _x: {body}"
            if body_node:
                self._warn(f"Multi-statement destructured arrow at L{node.start_point[0]+1}")
            return f"lambda _x: None  # TODO: multi-statement destructured arrow"

        # Non-destructured
        params = ", ".join(convert_name(n) for n in param_names)

        if body_expr is not None:
            body = self._node(body_expr)
            return f"lambda {params}: {body}"

        if body_node is None:
            return f"lambda {params}: None"

        # Multi-statement arrow
        self._warn(f"Multi-statement arrow function at L{node.start_point[0]+1} emitted as lambda")
        return f"lambda {params}: None  # TODO: multi-statement arrow"

    # -- literals and primitives --

    def _emit_object(self, node: Node) -> str:
        pairs = []
        for child in named_children(node):
            if child.type == "pair":
                key_node = self._field(child, "key")
                val_node = self._field(child, "value")
                key = self._get_text(key_node) if key_node else "?"
                val = self._node(val_node) if val_node else "None"
                pairs.append(f'"{key}": {val}')
            elif child.type == "shorthand_property_identifier":
                name = self._get_text(child)
                py_name = convert_name(name)
                pairs.append(f'"{name}": {py_name}')
            elif child.type == "spread_element":
                inner = named_children(child)
                if inner:
                    val = self._node(inner[0])
                    pairs.append(f"**{val}")
        if not pairs:
            return "JSObj({})"
        if len(pairs) <= 3:
            return "JSObj({" + ", ".join(pairs) + "})"
        # Multi-line dict
        inner = ",\n".join(self._indent_str() + "    " + p for p in pairs)
        return "JSObj({\n" + inner + ",\n" + self._indent_str() + "})"

    def _emit_pair(self, node: Node) -> str:
        key_node = self._field(node, "key")
        val_node = self._field(node, "value")
        key = self._get_text(key_node) if key_node else "?"
        val = self._node(val_node) if val_node else "None"
        return f'"{key}": {val}'

    def _emit_array(self, node: Node) -> str:
        items = []
        for child in named_children(node):
            items.append(self._node(child))
        return "[" + ", ".join(items) + "]"

    def _emit_spread_element(self, node: Node) -> str:
        inner = named_children(node)
        if inner:
            return f"*{self._node(inner[0])}"
        return "*[]"

    def _emit_string(self, node: Node) -> str:
        return self._get_text(node)  # preserve quotes

    def _emit_string_fragment(self, node: Node) -> str:
        return self._get_text(node)

    def _emit_template_string(self, node: Node) -> str:
        # Convert to f-string
        parts = []
        for child in node.children:
            if child.type == "template_substitution":
                inner = named_children(child)
                if inner:
                    val = self._node(inner[0])
                    parts.append(f"{{{val}}}")
            elif child.is_named:
                parts.append(self._get_text(child))
            else:
                text = self._get_text(child)
                if text not in ("`",):
                    parts.append(text)
        content = "".join(parts)
        # Use triple-quoted f-string if content contains newlines
        if "\n" in content:
            return 'f"""' + content + '"""'
        return 'f"' + content + '"'

    def _emit_template_substitution(self, node: Node) -> str:
        inner = named_children(node)
        if inner:
            return f"{{{self._node(inner[0])}}}"
        return ""

    def _emit_number(self, node: Node) -> str:
        return self._get_text(node)

    def _emit_true(self, node: Node) -> str:
        return "True"

    def _emit_false(self, node: Node) -> str:
        return "False"

    def _emit_undefined(self, node: Node) -> str:
        return "None"

    def _emit_null(self, node: Node) -> str:
        return "None"

    def _emit_identifier(self, node: Node) -> str:
        name = self._get_text(node)
        # Special TS identifiers
        if name == "undefined":
            return "None"
        if name == "null":
            return "None"
        if name == "this":
            return "self"
        # Check rename context (used for inlining destructured arrow bodies)
        if name in self._rename_ctx:
            return self._rename_ctx[name]
        return convert_name(name)

    def _emit_property_identifier(self, node: Node) -> str:
        return self._get_text(node)  # keep original for attribute access

    def _emit_this(self, node: Node) -> str:
        return "self"

    def _emit_comment(self, node: Node) -> str:
        text = self._get_text(node).strip()
        if text.startswith("//"):
            return self._line(f"# {text[2:].strip()}", node)
        if text.startswith("/*") and text.endswith("*/"):
            inner = text[2:-2].strip()
            lines = inner.split("\n")
            if len(lines) == 1:
                return self._line(f"# {lines[0].strip()}", node)
            result = []
            for line in lines:
                cleaned = line.strip().lstrip("* ").strip()
                if cleaned:
                    result.append(self._line(f"# {cleaned}", node))
            return "\n".join(result)
        return self._line(f"# {text}", node)

    # -- types (all stripped) --

    def _emit_type_annotation(self, node: Node) -> str:
        return ""

    def _emit_type_identifier(self, node: Node) -> str:
        return ""

    def _emit_predefined_type(self, node: Node) -> str:
        return ""

    def _emit_object_type(self, node: Node) -> str:
        return ""

    def _emit_array_type(self, node: Node) -> str:
        return ""

    def _emit_index_signature(self, node: Node) -> str:
        return ""

    def _emit_intersection_type(self, node: Node) -> str:
        return ""

    def _emit_property_signature(self, node: Node) -> str:
        return ""

    def _emit_as_expression(self, node: Node) -> str:
        # Type cast: expr as Type → just emit the expression
        inner = named_children(node)
        if inner:
            return self._node(inner[0])
        return ""

    # -- import helpers (skip, handled by import_statement) --

    def _emit_import_clause(self, node: Node) -> str:
        return ""

    def _emit_named_imports(self, node: Node) -> str:
        return ""

    def _emit_import_specifier(self, node: Node) -> str:
        return ""

    # -- destructuring patterns --

    def _emit_object_pattern(self, node: Node) -> str:
        names = []
        for child in named_children(node):
            if child.type == "shorthand_property_identifier_pattern":
                names.append(convert_name(self._get_text(child)))
            elif child.type == "pair_pattern" or child.type == "pair":
                key = self._field(child, "key")
                if key:
                    names.append(convert_name(self._get_text(key)))
        return ", ".join(names) if names else "_"

    def _emit_shorthand_property_identifier_pattern(self, node: Node) -> str:
        return convert_name(self._get_text(node))

    def _emit_shorthand_property_identifier(self, node: Node) -> str:
        name = self._get_text(node)
        py_name = convert_name(name)
        return f'"{name}": {py_name}'

    # -- higher-order array methods → comprehensions --

    def _get_arrow_arg(self, args_node: Node | None):
        """Get the first arrow_function argument node, or None."""
        if args_node is None:
            return None
        for child in named_children(args_node):
            if child.type == "arrow_function":
                return child
        return None

    def _inline_arrow_condition(self, arrow: Node, item_var: str) -> str:
        """Inline an arrow function body as a condition expression,
        handling destructured params via rename context."""
        param_names, is_destructured, body_expr, _ = self._extract_arrow_info(arrow)
        if body_expr is not None:
            return self._emit_arrow_body_with_rename(
                body_expr, param_names, is_destructured, item_var
            )
        # Fallback: emit as lambda call
        lam = self._node(arrow)
        return f"{lam}({item_var})"

    def _emit_filter_call(self, obj_node: Node | None, args_node: Node | None) -> str:
        obj = self._node(obj_node) if obj_node else "[]"
        arrow = self._get_arrow_arg(args_node)
        if arrow is not None:
            cond = self._inline_arrow_condition(arrow, "_x")
            return f"[_x for _x in {obj} if {cond}]"
        args = self._emit_args_list(args_node) if args_node else []
        if args:
            return f"[_x for _x in {obj} if {args[0]}(_x)]"
        return obj

    def _emit_map_call(self, obj_node: Node | None, args_node: Node | None) -> str:
        obj = self._node(obj_node) if obj_node else "[]"
        arrow = self._get_arrow_arg(args_node)
        if arrow is not None:
            expr = self._inline_arrow_condition(arrow, "_x")
            return f"[{expr} for _x in {obj}]"
        args = self._emit_args_list(args_node) if args_node else []
        if args:
            return f"[{args[0]}(_x) for _x in {obj}]"
        return obj

    def _emit_find_call(self, obj_node: Node | None, args_node: Node | None) -> str:
        obj = self._node(obj_node) if obj_node else "[]"
        arrow = self._get_arrow_arg(args_node)
        if arrow is not None:
            cond = self._inline_arrow_condition(arrow, "_x")
            return f"next((_x for _x in {obj} if {cond}), None)"
        args = self._emit_args_list(args_node) if args_node else []
        if args:
            return f"next((_x for _x in {obj} if {args[0]}(_x)), None)"
        return "None"

    def _emit_find_index_call(self, obj_node: Node | None, args_node: Node | None) -> str:
        obj = self._node(obj_node) if obj_node else "[]"
        arrow = self._get_arrow_arg(args_node)
        if arrow is not None:
            cond = self._inline_arrow_condition(arrow, "_x")
            return f"next((_i for _i, _x in enumerate({obj}) if {cond}), -1)"
        args = self._emit_args_list(args_node) if args_node else []
        if args:
            return f"next((_i for _i, _x in enumerate({obj}) if {args[0]}(_x)), -1)"
        return "-1"

    def _emit_foreach_call(self, obj_node: Node | None, args_node: Node | None) -> str:
        obj = self._node(obj_node) if obj_node else "[]"
        args = self._emit_args_list(args_node) if args_node else []
        if args:
            header = self._line(f"for _x in {obj}:")
            self._indent += 1
            body = self._line(f"{args[0]}(_x)")
            self._indent -= 1
            return f"{header}\n{body}"
        return self._line("pass  # forEach")
