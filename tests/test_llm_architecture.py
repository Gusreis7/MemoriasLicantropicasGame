"""Limites arquiteturais da integração LLM, independentes de credenciais AWS."""

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "src"


def test_application_has_flat_src_package_and_no_regex_imports():
    assert (SOURCE / "main.py").is_file()
    assert not (SOURCE / "memorias_licantropicas").exists()
    forbidden = {"re", "regex", "memorias_licantropicas"}
    violations = []
    for path in SOURCE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules = [node.module]
            for module in modules:
                if module.split(".", 1)[0] in forbidden:
                    violations.append(f"{path.relative_to(ROOT)}:{node.lineno}: {module}")
    assert not violations, "\n".join(violations)


def test_output_pipeline_uses_framework_tools_parser_without_text_json_decoder():
    path = SOURCE / "infrastructure" / "llm" / "structured.py"
    tree = ast.parse(path.read_text())
    assert any(
        isinstance(node, ast.ImportFrom)
        and node.module == "langchain_core.output_parsers.openai_tools"
        and any(alias.name == "PydanticToolsParser" for alias in node.names)
        for node in ast.walk(tree)
    )
    assert not any(
        isinstance(node, ast.Import) and any(alias.name == "json" for alias in node.names)
        or isinstance(node, ast.ImportFrom) and node.module == "json"
        for node in ast.walk(tree)
    )
    assert not (SOURCE / "infrastructure" / "llm" / "json_output.py").exists()
    assert not (SOURCE / "infrastructure" / "legacy_history.py").exists()
    assert not (SOURCE / "modules" / "agents" / "output.py").exists()
