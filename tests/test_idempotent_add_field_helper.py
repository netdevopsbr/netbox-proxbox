"""Regression tests for additive migration fields retired by current models."""

from __future__ import annotations

import importlib.util
import sys
import types
from types import SimpleNamespace
from pathlib import Path


class FieldDoesNotExist(LookupError):
    """Minimal stand-in for Django's historical model-field lookup error."""


def _load_helper(monkeypatch):
    django_db = types.ModuleType("django.db")
    django_core = types.ModuleType("django.core")
    django_core_exceptions = types.ModuleType("django.core.exceptions")
    django_core_exceptions.FieldDoesNotExist = FieldDoesNotExist
    monkeypatch.setitem(sys.modules, "django.db", django_db)
    monkeypatch.setitem(sys.modules, "django.core", django_core)
    monkeypatch.setitem(sys.modules, "django.core.exceptions", django_core_exceptions)
    monkeypatch.setattr(
        django_core, "exceptions", django_core_exceptions, raising=False
    )
    django_parent = sys.modules.get("django")
    if django_parent is not None:
        monkeypatch.setattr(django_parent, "db", django_db, raising=False)
        monkeypatch.setattr(django_parent, "core", django_core, raising=False)

    migration_module = types.ModuleType("django.db.migrations")
    migration_module.__path__ = []

    class ProjectState:
        def __init__(self, apps):
            self.apps = apps

        @classmethod
        def from_apps(cls, apps):
            return cls(apps)

    migration_state_module = types.ModuleType("django.db.migrations.state")
    migration_state_module.ProjectState = ProjectState
    monkeypatch.setitem(
        sys.modules, "django.db.migrations.state", migration_state_module
    )

    class AddField:
        def __init__(self, model_name, name, field, preserve_default=True):
            self.model_name = model_name
            self.name = name
            self.field = field
            self.preserve_default = preserve_default

        def state_forwards(self, app_label, state):
            model = state.apps.get_model(app_label, self.model_name)
            fields = model._meta.fields
            field = self.field
            if not self.preserve_default:
                field_values = vars(self.field).copy()
                field_values["default"] = None
                field = SimpleNamespace(**field_values)
            fields[self.name] = field

            def get_field(name):
                if name not in fields:
                    raise FieldDoesNotExist(name)
                return fields[name]

            model._meta.get_field = get_field

    class RunPython:
        def __init__(self, code, reverse_code):
            self.code = code
            self.reverse_code = reverse_code

    class SeparateDatabaseAndState:
        def __init__(self, *, database_operations, state_operations):
            self.database_operations = database_operations
            self.state_operations = state_operations

    RunPython.noop = lambda *args, **kwargs: None
    migration_module.AddField = AddField
    migration_module.RunPython = RunPython
    migration_module.SeparateDatabaseAndState = SeparateDatabaseAndState
    monkeypatch.setitem(sys.modules, "django.db.migrations", migration_module)
    monkeypatch.setattr(django_db, "migrations", migration_module, raising=False)

    live_apps_module = types.ModuleType("django.apps")
    live_meta = SimpleNamespace(
        get_field=lambda name: (_ for _ in ()).throw(FieldDoesNotExist(name))
    )
    live_apps_module.apps = SimpleNamespace(
        get_model=lambda app_label, model_name: SimpleNamespace(_meta=live_meta)
    )
    monkeypatch.setitem(sys.modules, "django.apps", live_apps_module)
    if django_parent is not None:
        monkeypatch.setattr(django_parent, "apps", live_apps_module, raising=False)

    spec = importlib.util.spec_from_file_location(
        "idempotent_ops_under_test",
        Path(__file__).resolve().parents[1]
        / "netbox_proxbox"
        / "migrations"
        / "_idempotent_ops.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _SchemaEditor:
    def __init__(self, table: str, column_names: set[str]):
        class _Cursor:
            def __enter__(self):
                return self

            def __exit__(self, exc_type, exc_value, traceback):
                return False

        self.connection = SimpleNamespace(
            cursor=lambda: _Cursor(),
            introspection=SimpleNamespace(
                table_names=lambda cursor: [table],
                get_table_description=lambda cursor, name: [
                    SimpleNamespace(name=column) for column in column_names
                ],
            ),
        )
        self.added: list[tuple[object, object]] = []
        self.removed: list[tuple[object, object]] = []

    def add_field(self, model, field):
        self.added.append((model, field))

    def remove_field(self, model, field):
        self.removed.append((model, field))


def _model() -> SimpleNamespace:
    return SimpleNamespace(
        _meta=SimpleNamespace(
            db_table="netbox_proxbox_proxboxpluginsettings",
            fields={},
            get_field=lambda name: (_ for _ in ()).throw(FieldDoesNotExist(name)),
        )
    )


def _state_operation(helper, field, preserve_default=True):
    return helper.migrations.AddField(
        model_name="proxboxpluginsettings",
        name="custom_fields_enabled",
        field=field,
        preserve_default=preserve_default,
    )


def test_add_field_uses_historical_state_when_live_model_retired_field(
    monkeypatch,
) -> None:
    helper = _load_helper(monkeypatch)
    field = SimpleNamespace(column="custom_fields_enabled", default=False)
    model = _model()
    apps = SimpleNamespace(get_model=lambda app_label, model_name: model)
    schema_editor = _SchemaEditor(model._meta.db_table, {"id"})

    helper._add_field_if_missing(
        "proxboxpluginsettings",
        "custom_fields_enabled",
        _state_operation(helper, field),
    )(apps, schema_editor)

    assert schema_editor.added == [(model, field)]


def test_add_field_remains_idempotent_when_historical_column_exists(
    monkeypatch,
) -> None:
    helper = _load_helper(monkeypatch)
    field = SimpleNamespace(column="custom_fields_enabled", default=False)
    model = _model()
    apps = SimpleNamespace(get_model=lambda app_label, model_name: model)
    schema_editor = _SchemaEditor(model._meta.db_table, {"id", field.column})

    helper._add_field_if_missing(
        "proxboxpluginsettings",
        "custom_fields_enabled",
        _state_operation(helper, field),
    )(apps, schema_editor)

    assert schema_editor.added == []


def test_remove_field_does_not_delete_retired_column_on_reverse(monkeypatch) -> None:
    helper = _load_helper(monkeypatch)
    model = _model()
    apps = SimpleNamespace(get_model=lambda app_label, model_name: model)
    schema_editor = _SchemaEditor(model._meta.db_table, {"id", "custom_fields_enabled"})

    helper._remove_field_if_present("proxboxpluginsettings", "custom_fields_enabled")(
        apps, schema_editor
    )

    assert schema_editor.removed == []


def test_add_field_restores_one_time_default_for_non_preserved_defaults(
    monkeypatch,
) -> None:
    helper = _load_helper(monkeypatch)
    field = SimpleNamespace(column="custom_fields_enabled", default="sentinel")
    historical_model = _model()
    live_model = _model()
    live_model._meta.fields["custom_fields_enabled"] = field
    live_model._meta.get_field = lambda name: live_model._meta.fields[name]
    monkeypatch.setattr(
        helper.live_apps,
        "get_model",
        lambda app_label, model_name: live_model,
    )
    apps = SimpleNamespace(get_model=lambda app_label, model_name: historical_model)
    schema_editor = _SchemaEditor(historical_model._meta.db_table, {"id"})

    helper._add_field_if_missing(
        "proxboxpluginsettings",
        "custom_fields_enabled",
        _state_operation(helper, field, preserve_default=False),
    )(apps, schema_editor)

    assert schema_editor.added[0][1].default == "sentinel"


def test_remove_field_does_not_delete_existing_current_column_on_reverse(
    monkeypatch,
) -> None:
    helper = _load_helper(monkeypatch)
    field = SimpleNamespace(column="current_field")
    model = _model()
    model._meta.fields["current_field"] = field
    model._meta.get_field = lambda name: model._meta.fields[name]
    monkeypatch.setattr(
        helper.live_apps,
        "get_model",
        lambda app_label, model_name: model,
    )
    apps = SimpleNamespace(get_model=lambda app_label, model_name: model)
    schema_editor = _SchemaEditor(model._meta.db_table, {"id", field.column})

    helper._remove_field_if_present("proxboxpluginsettings", "current_field")(
        apps, schema_editor
    )

    assert schema_editor.removed == []
