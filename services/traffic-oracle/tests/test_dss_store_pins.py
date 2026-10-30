"""Pins between the decision-support store and the units module (C-U, plan §5.2).

The units module keeps its dispatch INSERT as a function-local literal (``dispatch_insert`` inside
``create_dispatch``), so it cannot be imported: ``decision_support/store.py`` carries a byte-identical copy,
``DSS_DISPATCH_INSERT``.  This test reads ``units/router.py``'s SOURCE with ``ast`` and fails the moment the two
differ.  The dispatch audit row goes through the imported ``_audit`` and the event check is the imported
``_SQL_EVENT_CHECK`` — never copies, never a new SQL.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import traffic_oracle.decision_support as dss_pkg
from traffic_oracle.decision_support import store
from traffic_oracle.units import router as units_router

UNITS_SOURCE = Path(inspect.getsourcefile(units_router)).read_text(encoding="utf-8")
STORE_SOURCE = Path(inspect.getsourcefile(store)).read_text(encoding="utf-8")
DSS_DIR = Path(inspect.getsourcefile(dss_pkg)).parent


def _function(tree: ast.Module, name: str) -> ast.AsyncFunctionDef | ast.FunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)) and node.name == name:
            return node
    raise AssertionError(f"{name} not found")


def _local_literal(fn: ast.AST, var: str) -> str:
    for node in ast.walk(fn):
        if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == var for t in node.targets):
            assert isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
            return node.value.value
    raise AssertionError(f"{var} not found")


def test_the_dispatch_insert_copy_is_byte_identical():
    original = _local_literal(_function(ast.parse(UNITS_SOURCE), "create_dispatch"), "dispatch_insert")
    assert store.DSS_DISPATCH_INSERT == original
    assert store.DSS_DISPATCH_INSERT.encode("utf-8") == original.encode("utf-8")
    assert "'requested'" in original  # a REQUEST: an officer still decides it


def test_audit_and_event_check_are_imported_not_copied():
    assert store._audit is units_router._audit
    assert store._SQL_EVENT_CHECK is units_router._SQL_EVENT_CHECK
    tree = ast.parse(STORE_SOURCE)
    defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    assigned = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets
                if isinstance(t, ast.Name)}
    assert "_audit" not in defined
    assert "_SQL_EVENT_CHECK" not in assigned
    imports = [n for n in tree.body if isinstance(n, ast.ImportFrom) and n.module == "traffic_oracle.units.router"]
    names = {a.name for n in imports for a in n.names}
    assert {"_audit", "_SQL_EVENT_CHECK"} <= names


def test_no_decision_support_module_writes_the_audit_or_dispatch_tables_itself():
    """Only the pinned copy inserts into corridor.dispatches; nothing here writes the audit tail or updates a
    dispatch (each request is decided on its own, through the units module)."""
    for path in sorted(DSS_DIR.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        assert "INSERT INTO corridor.dispatch_events" not in text, path.name
        assert "UPDATE corridor.dispatches" not in text, path.name
        count = text.count("INSERT INTO corridor.dispatches")
        assert count == (1 if path.name == "store.py" else 0), path.name
        assert "simulation." not in "\n".join(
            line for line in text.splitlines() if line.lstrip().startswith(("INSERT", "UPDATE", "DELETE"))
        )


def test_the_twin_is_reused_unchanged():
    """The wargame calls the twin's own route function and gate; decision support never edits simulation/."""
    from traffic_oracle.decision_support import wargame

    src = inspect.getsource(wargame.twin_disruption)
    assert "simulate_twin(req, request)" in src
    assert "signal_policy_gate.shared()" in src
    assert "from traffic_oracle.simulation.router import" in src
