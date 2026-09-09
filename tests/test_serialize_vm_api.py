"""Contract tests for proxbox VM resource serialization."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
VIEWS_PATH = REPO_ROOT / "netbox_proxbox" / "api" / "views.py"


def _serialize_vm_source() -> str:
    module = ast.parse(VIEWS_PATH.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.FunctionDef) and node.name == "_serialize_vm":
            return (
                ast.get_source_segment(VIEWS_PATH.read_text(encoding="utf-8"), node)
                or ""
            )
    raise AssertionError("_serialize_vm not found in api/views.py")


def test_serialize_vm_includes_hardware_and_status_fields() -> None:
    source = _serialize_vm_source()
    module_source = VIEWS_PATH.read_text(encoding="utf-8")
    for token in (
        '"status": status_payload',
        '"proxmox_status": proxmox_status',
        '"vcpus": vm.vcpus',
        '"memory": vm.memory',
        '"disk": vm.disk',
        "vm.get_status_display()",
    ):
        assert token in source, f"missing token in _serialize_vm: {token!r}"
    for token in ("def _vm_proxmox_status", "proxbox_sync_state"):
        assert token in module_source, f"missing token in api/views.py: {token!r}"
