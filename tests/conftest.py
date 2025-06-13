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

    class DummyFont:
        def __init__(self, *a, **kw):
            pass

    dummy.CTk = DummyCTk
    dummy.CTkLabel = DummyWidget
    dummy.CTkEntry = DummyWidget
    dummy.CTkOptionMenu = DummyWidget
    dummy.CTkFrame = DummyWidget
    dummy.CTkProgressBar = DummyWidget
    dummy.CTkButton = DummyWidget
    dummy.CTkFont = DummyFont
    dummy.IntVar = DummyVar
    dummy.StringVar = DummyVar
    dummy.set_appearance_mode = lambda *a, **kw: None

    monkeypatch.setitem(sys.modules, 'customtkinter', dummy)

    mb = types.SimpleNamespace(
        showinfo=lambda *a, **kw: None,
        showwarning=lambda *a, **kw: None,
        showerror=lambda *a, **kw: None,
    )
    monkeypatch.setitem(sys.modules, 'tkinter.messagebox', mb)
    yield

