import ast
from dataclasses import dataclass
from pathlib import Path

import pytest

import atda


@dataclass(frozen=True)
class Violation:
    path: Path
    line: int


def find_adapter_imports(root: Path) -> list[Violation]:
    package = root.name
    violations = []
    for path in sorted(root.rglob("*.py")):
        relative = path.relative_to(root)
        if relative.parts[0] == "adapters":
            continue
        # A module belongs to the package in its directory, __init__.py included.
        home = [package, *relative.parts[:-1]]
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import | ast.ImportFrom) and _imports_adapters(
                node, package, home
            ):
                violations.append(Violation(path, node.lineno))
    return violations


def _imports_adapters(node: ast.Import | ast.ImportFrom, package: str, home: list[str]) -> bool:
    adapters = [package, "adapters"]
    if isinstance(node, ast.Import):
        return any(alias.name.split(".")[:2] == adapters for alias in node.names)
    base = home[: len(home) - (node.level - 1)] if node.level else []
    target = [*base, *(node.module.split(".") if node.module else [])]
    if target[:2] == adapters:
        return True
    return target == [package] and any(alias.name == "adapters" for alias in node.names)


VIOLATIONS = [
    ("pipeline.py", "import atda.adapters\n"),
    ("pipeline.py", "import atda.adapters.ollama as ollama\n"),
    ("pipeline.py", "from atda.adapters import ollama\n"),
    ("pipeline.py", "from atda.adapters.ollama import OllamaClient\n"),
    ("pipeline.py", "from atda import adapters\n"),
    ("pipeline.py", "from .adapters import ollama\n"),
    ("pipeline.py", "from . import adapters\n"),
    ("agents/designer.py", "from ..adapters.ollama import OllamaClient\n"),
    ("agents/designer.py", "from .. import adapters\n"),
    ("agents/__init__.py", "from ..adapters import ollama\n"),
]

CLEAN = [
    ("pipeline.py", "import os\nimport atda.ports\n"),
    ("pipeline.py", "from atda.ports.llm import LLMClient\n"),
    ("pipeline.py", "from atda import ports\n"),
    ("pipeline.py", "import adapters\n"),
    ("agents/designer.py", "from ..ports import llm\n"),
    ("agents/designer.py", "from . import analyst\n"),
]


def write_package(tmp_path: Path, files: dict[str, str]) -> Path:
    root = tmp_path / "atda"
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    return root


@pytest.mark.parametrize(("name", "source"), VIOLATIONS)
def test_core_import_from_adapters_is_reported(tmp_path: Path, name: str, source: str) -> None:
    root = write_package(tmp_path, {name: "import os\n\n" + source})

    violations = find_adapter_imports(root)

    assert [(v.path, v.line) for v in violations] == [(root / name, 3)]


@pytest.mark.parametrize(("name", "source"), CLEAN)
def test_core_without_adapter_imports_is_accepted(tmp_path: Path, name: str, source: str) -> None:
    root = write_package(tmp_path, {name: source})

    assert find_adapter_imports(root) == []


def test_modules_inside_adapters_are_not_checked(tmp_path: Path) -> None:
    root = write_package(
        tmp_path,
        {
            "adapters/__init__.py": "from .ollama import OllamaClient\n",
            "adapters/ollama.py": "from atda.adapters import http\nfrom atda.ports import llm\n",
        },
    )

    assert find_adapter_imports(root) == []


def test_every_violation_in_a_tree_is_reported(tmp_path: Path) -> None:
    root = write_package(
        tmp_path,
        {
            "pipeline.py": "import atda.adapters\n",
            "agents/designer.py": "from atda.adapters import a\nfrom atda.adapters import b\n",
        },
    )

    violations = find_adapter_imports(root)

    assert sorted((v.path.name, v.line) for v in violations) == [
        ("designer.py", 1),
        ("designer.py", 2),
        ("pipeline.py", 1),
    ]


def test_the_real_core_never_imports_from_adapters() -> None:
    assert find_adapter_imports(Path(atda.__file__).parent) == []
