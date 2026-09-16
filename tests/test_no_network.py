"""Offline by construction.

Shipped code must not be able to reach the network. This walks the AST of every
module under src/ rather than grepping, so a module cannot hide an import inside
a function body or an alias.
"""

from __future__ import annotations

import ast

from tests.conftest import SRC_ROOT, iter_source_files

FORBIDDEN_MODULES = frozenset(
    {
        "socket",
        "ssl",
        "urllib",
        "urllib2",
        "urllib3",
        "http",
        "httpx",
        "requests",
        "ftplib",
        "smtplib",
        "poplib",
        "imaplib",
        "telnetlib",
        "xmlrpc",
        "webbrowser",
        "aiohttp",
        "websockets",
    }
)

FORBIDDEN_CALL_NAMES = frozenset({"urlopen", "urlretrieve", "socket", "create_connection"})


def _root_module(name: str) -> str:
    return name.split(".", 1)[0]


def test_no_shipped_module_imports_networking() -> None:
    offenders: list[str] = []
    for path in iter_source_files((".py",)):
        relative = path.relative_to(SRC_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _root_module(alias.name) in FORBIDDEN_MODULES:
                        offenders.append(f"{relative}:{node.lineno}: import {alias.name}")
            elif (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and _root_module(node.module) in FORBIDDEN_MODULES
            ):
                offenders.append(f"{relative}:{node.lineno}: from {node.module} import ...")
    assert not offenders, "shipped code must never import networking:\n" + "\n".join(offenders)


def test_no_shipped_module_calls_network_helpers() -> None:
    offenders: list[str] = []
    for path in iter_source_files((".py",)):
        relative = path.relative_to(SRC_ROOT).as_posix()
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            name = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr
                if isinstance(func, ast.Attribute)
                else None
            )
            if name in FORBIDDEN_CALL_NAMES:
                offenders.append(f"{relative}:{node.lineno}: call to {name}()")
            if name == "__import__" and node.args:
                first = node.args[0]
                if (
                    isinstance(first, ast.Constant)
                    and isinstance(first.value, str)
                    and _root_module(first.value) in FORBIDDEN_MODULES
                ):
                    offenders.append(f"{relative}:{node.lineno}: __import__({first.value!r})")
    assert not offenders, "shipped code must never call network helpers:\n" + "\n".join(offenders)
