"""Tests for the TypeScript parser module."""
from __future__ import annotations

import pytest
from pathlib import Path
from tt.ts_parser import (
    parse_typescript,
    parse_file,
    find_nodes,
    find_first,
    child_by_type,
    children_by_type,
    named_children,
    node_text,
    dump_tree,
    summary,
)

REPO_ROOT = Path(__file__).parent.parent.parent

ROAI_FILE = (
    REPO_ROOT / "projects" / "ghostfolio" / "apps" / "api" / "src"
    / "app" / "portfolio" / "calculator" / "roai" / "portfolio-calculator.ts"
)

BASE_FILE = (
    REPO_ROOT / "projects" / "ghostfolio" / "apps" / "api" / "src"
    / "app" / "portfolio" / "calculator" / "portfolio-calculator.ts"
)


# ── Basic parsing ──────────────────────────────────────────────

class TestBasicParsing:
    def test_parse_simple_string(self):
        result = parse_typescript("const x = 42;")
        assert not result.has_errors
        assert result.root.type == "program"

    def test_parse_empty_string(self):
        result = parse_typescript("")
        assert not result.has_errors

    def test_parse_bytes(self):
        result = parse_typescript(b"let y: string = 'hello';")
        assert not result.has_errors

    def test_source_for_node(self):
        result = parse_typescript("const x = 42;")
        decl = find_first(result.root, "lexical_declaration")
        assert result.source_for(decl) == "const x = 42;"

    def test_line_access(self):
        result = parse_typescript("line one\nline two\nline three")
        assert result.line(1) == "line one"
        assert result.line(2) == "line two"
        assert result.line(3) == "line three"
        assert result.line(0) == ""
        assert result.line(99) == ""

    def test_parse_errors_detected(self):
        result = parse_typescript("const x = ;")  # missing value
        assert result.has_errors
        assert len(result.errors) > 0


# ── Node navigation ───────────────────────────────────────────

class TestNodeNavigation:
    def test_find_nodes(self):
        result = parse_typescript("const a = 1; const b = 2; let c = 3;")
        decls = find_nodes(result.root, "lexical_declaration")
        assert len(decls) == 3

    def test_find_first(self):
        result = parse_typescript("function foo() { return 42; }")
        ret = find_first(result.root, "return_statement")
        assert ret is not None
        assert ret.type == "return_statement"

    def test_find_first_not_found(self):
        result = parse_typescript("const x = 1;")
        assert find_first(result.root, "class_declaration") is None

    def test_named_children(self):
        result = parse_typescript("const x = 1;")
        root_named = named_children(result.root)
        # Should filter out whitespace/punctuation at top level
        assert all(c.is_named for c in root_named)

    def test_child_by_type(self):
        result = parse_typescript("const x = 1;")
        decl = child_by_type(result.root, "lexical_declaration")
        assert decl is not None
        assert decl.type == "lexical_declaration"

    def test_children_by_type(self):
        result = parse_typescript("const a = 1; const b = 2; let c = 3;")
        decls = children_by_type(result.root, "lexical_declaration")
        assert len(decls) == 3

    def test_node_text(self):
        result = parse_typescript("const x = 42;")
        decl = find_first(result.root, "lexical_declaration")
        assert node_text(decl) == "const x = 42;"


# ── TypeScript construct recognition ──────────────────────────

class TestTypeScriptConstructs:
    def test_class_with_extends(self):
        code = "export class Foo extends Bar { x: number; }"
        result = parse_typescript(code)
        assert not result.has_errors
        cls = find_first(result.root, "class_declaration")
        assert cls is not None
        name = cls.child_by_field_name("name")
        assert node_text(name) == "Foo"

    def test_method_definition(self):
        code = """
        class C {
            public getValue(): number {
                return 42;
            }
        }
        """
        result = parse_typescript(code)
        assert not result.has_errors
        method = find_first(result.root, "method_definition")
        assert method is not None

    def test_arrow_function(self):
        code = "const fn = (x: number) => x + 1;"
        result = parse_typescript(code)
        assert not result.has_errors
        arrow = find_first(result.root, "arrow_function")
        assert arrow is not None

    def test_new_expression(self):
        code = "const x = new Big(0);"
        result = parse_typescript(code)
        assert not result.has_errors
        new_expr = find_first(result.root, "new_expression")
        assert new_expr is not None
        assert "Big" in node_text(new_expr)

    def test_member_expression_chain(self):
        code = "const y = a.plus(b.mul(c));"
        result = parse_typescript(code)
        assert not result.has_errors
        members = find_nodes(result.root, "member_expression")
        assert len(members) >= 2  # a.plus and b.mul

    def test_optional_chaining(self):
        code = "const z = obj?.prop?.value;"
        result = parse_typescript(code)
        assert not result.has_errors
        opt = find_nodes(result.root, "optional_chain")
        assert len(opt) >= 1

    def test_nullish_coalescing(self):
        code = "const x = a ?? b;"
        result = parse_typescript(code)
        assert not result.has_errors
        binexp = find_first(result.root, "binary_expression")
        assert binexp is not None
        assert "??" in node_text(binexp)

    def test_ternary_expression(self):
        code = "const x = cond ? a : b;"
        result = parse_typescript(code)
        assert not result.has_errors
        tern = find_first(result.root, "ternary_expression")
        assert tern is not None

    def test_for_of_loop(self):
        code = "for (const item of items) { console.log(item); }"
        result = parse_typescript(code)
        assert not result.has_errors
        forin = find_first(result.root, "for_in_statement")
        assert forin is not None

    def test_template_literal(self):
        code = "const s = `hello ${name}`;"
        result = parse_typescript(code)
        assert not result.has_errors
        tmpl = find_first(result.root, "template_string")
        assert tmpl is not None

    def test_object_destructuring_param(self):
        code = """
        class C {
            method({ a, b, c }: { a: number; b: string; c: boolean }) {
                return a;
            }
        }
        """
        result = parse_typescript(code)
        assert not result.has_errors
        pattern = find_first(result.root, "object_pattern")
        assert pattern is not None

    def test_type_annotation_stripped(self):
        code = "let x: number = 5;"
        result = parse_typescript(code)
        assert not result.has_errors
        ann = find_first(result.root, "type_annotation")
        assert ann is not None

    def test_interface(self):
        code = "interface Foo { bar: string; baz: number; }"
        result = parse_typescript(code)
        assert not result.has_errors
        iface = find_first(result.root, "interface_declaration")
        assert iface is not None

    def test_enum(self):
        code = "enum Color { Red = 'RED', Blue = 'BLUE' }"
        result = parse_typescript(code)
        assert not result.has_errors
        enum = find_first(result.root, "enum_declaration")
        assert enum is not None

    def test_shorthand_property(self):
        code = "const obj = { x, y, z };"
        result = parse_typescript(code)
        assert not result.has_errors
        shorthands = find_nodes(result.root, "shorthand_property_identifier")
        assert len(shorthands) == 3

    def test_index_signature(self):
        code = """
        class C {
            method(): { [key: string]: Big } {
                return {};
            }
        }
        """
        result = parse_typescript(code)
        assert not result.has_errors
        idx = find_first(result.root, "index_signature")
        assert idx is not None


# ── Real file parsing ─────────────────────────────────────────

@pytest.mark.skipif(not ROAI_FILE.exists(), reason="Ghostfolio source not present")
class TestRoaiFile:
    @pytest.fixture(scope="class")
    def parsed(self):
        return parse_file(ROAI_FILE)

    def test_no_parse_errors(self, parsed):
        assert not parsed.has_errors, f"Parse errors: {parsed.errors}"

    def test_has_imports(self, parsed):
        imports = find_nodes(parsed.root, "import_statement")
        assert len(imports) == 13  # exact count from the file

    def test_has_class(self, parsed):
        cls = find_first(parsed.root, "class_declaration")
        assert cls is not None
        name = cls.child_by_field_name("name")
        assert node_text(name) == "RoaiPortfolioCalculator"

    def test_class_extends(self, parsed):
        cls = find_first(parsed.root, "class_declaration")
        heritage = child_by_type(cls, "class_heritage")
        assert heritage is not None
        assert "PortfolioCalculator" in node_text(heritage)

    def test_has_three_methods(self, parsed):
        methods = find_nodes(parsed.root, "method_definition")
        assert len(methods) == 3

    def test_method_names(self, parsed):
        methods = find_nodes(parsed.root, "method_definition")
        names = []
        for m in methods:
            for c in m.children:
                if c.type == "property_identifier":
                    names.append(node_text(c))
                    break
        assert names == [
            "calculateOverallPerformance",
            "getPerformanceCalculationType",
            "getSymbolMetrics",
        ]

    def test_get_symbol_metrics_is_largest(self, parsed):
        methods = find_nodes(parsed.root, "method_definition")
        sizes = []
        for m in methods:
            lines = m.end_point[0] - m.start_point[0] + 1
            sizes.append(lines)
        assert max(sizes) == sizes[-1]  # getSymbolMetrics is last and largest
        assert max(sizes) > 800  # ~879 lines

    def test_big_js_usage(self, parsed):
        """The file should have many new Big() calls."""
        new_exprs = find_nodes(parsed.root, "new_expression")
        big_exprs = [
            n for n in new_exprs
            if any(c.type == "identifier" and node_text(c) == "Big" for c in n.children)
        ]
        assert len(big_exprs) > 50

    def test_has_arrow_functions(self, parsed):
        arrows = find_nodes(parsed.root, "arrow_function")
        assert len(arrows) >= 5

    def test_has_ternary_expressions(self, parsed):
        terns = find_nodes(parsed.root, "ternary_expression")
        assert len(terns) >= 10

    def test_has_for_loops(self, parsed):
        loops = find_nodes(parsed.root, "for_in_statement")
        assert len(loops) >= 3

    def test_has_optional_chaining(self, parsed):
        opts = find_nodes(parsed.root, "optional_chain")
        assert len(opts) >= 5


@pytest.mark.skipif(not BASE_FILE.exists(), reason="Ghostfolio source not present")
class TestBaseCalculatorFile:
    def test_parses_without_errors(self):
        result = parse_file(BASE_FILE)
        assert not result.has_errors
