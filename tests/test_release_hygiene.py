"""Mock devices may never ship, and shipped code may never run a shell.

These checks guard the packaging boundary: anything that fakes a camera lives
under tests/, and release artifacts are verified separately by
packaging/verify_release.py, which applies the same rules to a built folder.
"""

from __future__ import annotations

import ast

from tests.conftest import REPO_ROOT, SRC_ROOT, iter_source_files

MOCK_MARKERS = ("MOCK CAMERA", "mock_device", "MockCamera", "fake_camera")


def test_no_mock_device_code_under_src() -> None:
    offenders: list[str] = []
    for path in iter_source_files((".py", ".yaml", ".yml")):
        relative = path.relative_to(SRC_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        for marker in MOCK_MARKERS:
            if marker in text:
                offenders.append(f"{relative}: contains {marker!r}")
        if "mock" in path.name.lower():
            offenders.append(f"{relative}: mock module must live under tests/")
    assert not offenders, "mock camera code must not be shipped:\n" + "\n".join(offenders)


def test_developer_mock_package_lives_under_tests() -> None:
    devmock = REPO_ROOT / "tests" / "devmock"
    assert devmock.is_dir(), "tests/devmock/ is the only permitted home for mock devices"
    assert (devmock / "__init__.py").is_file()


#: Fully-qualified calls that hand a string to a shell or an interpreter.
#: platform.system() is a different function that merely shares a name, so the
#: owner is checked too rather than matching on the attribute alone.
FORBIDDEN_CALLS = frozenset({"os.system", "os.popen", "subprocess.getoutput"})
FORBIDDEN_BARE_CALLS = frozenset({"eval", "exec", "compile"})


def _dotted_name(node: ast.expr) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _dotted_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return None


def test_no_shell_execution_in_shipped_code() -> None:
    """subprocess is allowed (ExifTool), shell=True and os.system are not."""
    offenders: list[str] = []
    for path in iter_source_files((".py",)):
        relative = path.relative_to(SRC_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = _dotted_name(node.func)
            if name in FORBIDDEN_CALLS or name in FORBIDDEN_BARE_CALLS:
                offenders.append(f"{relative}:{node.lineno}: call to {name}()")
            for keyword in node.keywords:
                if keyword.arg == "shell" and not (
                    isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                ):
                    offenders.append(f"{relative}:{node.lineno}: shell= is not False")
    assert not offenders, "shipped code must not execute shells:\n" + "\n".join(offenders)


def test_the_shell_guard_actually_catches_a_shell_call(tmp_path: object) -> None:
    """A guard nobody has seen fail is not a guard."""
    tree = ast.parse("import os\nos.system('rm -rf /')\nsubprocess.run(x, shell=True)\n")
    found = [
        _dotted_name(node.func)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and _dotted_name(node.func) in FORBIDDEN_CALLS
    ]
    shell_kwargs = [
        keyword
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        for keyword in node.keywords
        if keyword.arg == "shell"
    ]

    assert found == ["os.system"]
    assert len(shell_kwargs) == 1


def test_platform_system_is_not_mistaken_for_os_system() -> None:
    tree = ast.parse("import platform\nplatform.system()\n")
    names = [_dotted_name(node.func) for node in ast.walk(tree) if isinstance(node, ast.Call)]

    assert names == ["platform.system"]
    assert not set(names) & FORBIDDEN_CALLS
