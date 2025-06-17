import sys
import types
import sqlite3
import hashlib
import os
import tempfile
import pytest

from database.init_db import initialize_database

# Fixture to create a temporary database using the provided schema
@pytest.fixture()
def temp_db(tmp_path):
    db_path = tmp_path / 'test.db'
    initialize_database(str(db_path))
    yield str(db_path)

# Fixture to replace customtkinter and tkinter.messagebox with dummies so GUI
# components can be instantiated in a headless test environment
@pytest.fixture(autouse=True)
def dummy_gui(monkeypatch):
    dummy = types.ModuleType('customtkinter')

    class DummyVar:
        def __init__(self, value=None):
            self._value = value
        def get(self):
            return self._value
        def set(self, value):
            self._value = value

    class DummyWidget:
        def __init__(self, *a, **kw):
            pass
        def pack(self, *a, **kw):
            pass
        def grid(self, *a, **kw):
            pass
        def bind(self, *a, **kw):
            pass
        def configure(self, *a, **kw):
            pass
        def set(self, *a, **kw):
            pass
        def destroy(self, *a, **kw):
            pass
        def cget(self, *a, **kw):
            return ""
        def winfo_children(self):
            return []
        def focus_set(self):
            pass

    class DummyCTk(DummyWidget):
        def title(self, *a, **kw):
            pass
        def geometry(self, *a, **kw):
            pass
        def destroy(self, *a, **kw):
            pass
        def after(self, *a, **kw):
            return 0
        def after_cancel(self, *a, **kw):
            pass
        def bell(self, *a, **kw):
            pass
        def protocol(self, *a, **kw):
            pass

    class DummyFont:
        def __init__(self, *a, **kw):
            pass

    class DummyTabview(DummyWidget):
        def add(self, name):
            return DummyWidget()

    dummy.CTk = DummyCTk # type: ignore[attr-defined]
    dummy.CTkLabel = DummyWidget # type: ignore[attr-defined]
    dummy.CTkEntry = DummyWidget # type: ignore[attr-defined]
    dummy.CTkOptionMenu = DummyWidget # type: ignore[attr-defined]
    dummy.CTkFrame = DummyWidget # type: ignore[attr-defined]
    dummy.CTkScrollableFrame = DummyWidget # type: ignore[attr-defined]
    dummy.CTkTabview = DummyTabview # type: ignore[attr-defined]
    dummy.CTkProgressBar = DummyWidget # type: ignore[attr-defined]
    dummy.CTkButton = DummyWidget # type: ignore[attr-defined]
    dummy.CTkFont = DummyFont # type: ignore[attr-defined]
    dummy.IntVar = DummyVar # type: ignore[attr-defined]
    dummy.StringVar = DummyVar # type: ignore[attr-defined]
    dummy.set_appearance_mode = lambda *a, **kw: None # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, 'customtkinter', dummy)

    ttk_dummy = types.ModuleType('tkinter.ttk')
    ttk_dummy.Treeview = DummyWidget
    monkeypatch.setitem(sys.modules, 'tkinter.ttk', ttk_dummy)

    mb = types.SimpleNamespace(
        showinfo=lambda *a, **kw: None,
        showwarning=lambda *a, **kw: None,
        showerror=lambda *a, **kw: None,
    )
    monkeypatch.setitem(sys.modules, 'tkinter.messagebox', mb)
    try:
        import tkinter
        monkeypatch.setattr(tkinter, 'messagebox', mb, raising=False)
    except Exception:
        pass
    yield

