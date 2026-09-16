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


def test_no_shell_execution_in_shipped_code() -> None:
    """subprocess is allowed (ExifTool), shell=True and os.system are not."""
    offenders: list[str] = []
    for path in iter_source_files((".py",)):
        relative = path.relative_to(SRC_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = func.attr if isinstance(func, ast.Attribute) else getattr(func, "id", None)
                if name in {"system", "popen", "eval", "exec"}:
                    offenders.append(f"{relative}:{node.lineno}: call to {name}()")
                for keyword in node.keywords:
                    if keyword.arg == "shell" and not (
                        isinstance(keyword.value, ast.Constant) and keyword.value.value is False
                    ):
                        offenders.append(f"{relative}:{node.lineno}: shell= is not False")
    assert not offenders, "shipped code must not execute shells:\n" + "\n".join(offenders)
