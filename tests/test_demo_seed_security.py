"""
The demo seeders create a council account, which can approve workers, verify
documents and read every row in the tenant. On a host anyone can reach, that
account's password is the entire security model -- so the seed is opt-in and the
password is overridable. These tests pin both, because either one silently
reverting would put a known administrator credential back on the internet.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"


def _load(name: str):
    """Import a script by path; they are run as `python scripts/<name>`, not a package."""
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def test_default_demo_password_is_local_only(monkeypatch):
    monkeypatch.delenv("SAHAKARSETU_DEMO_PASSWORD", raising=False)
    assert _load("seed_demo_data").demo_password() == "demo1234"


def test_demo_password_override_is_used_when_strong(monkeypatch):
    monkeypatch.setenv("SAHAKARSETU_DEMO_PASSWORD", "Str0ng-Demo-Pass-42")
    assert _load("seed_demo_data").demo_password() == "Str0ng-Demo-Pass-42"


@pytest.mark.parametrize("weak", ["short", "demo1234", "12345678901", "           "])
def test_a_weak_demo_password_override_is_refused(monkeypatch, weak):
    """A 12-character floor stops a hosted demo trading a known password for a guessable one."""
    monkeypatch.setenv("SAHAKARSETU_DEMO_PASSWORD", weak)
    with pytest.raises(SystemExit):
        _load("seed_demo_data").demo_password()


def test_seeding_works_with_the_default_council_code(monkeypatch, tmp_path):
    """The demo council code has a default again, so the seeder must not demand one."""
    monkeypatch.delenv("SAHAKARSETU_COUNCIL_CODE", raising=False)
    monkeypatch.setenv("SAHAKARSETU_DEMO_PASSWORD", "Str0ng-Demo-Pass-42")
    monkeypatch.setenv("SAHAKARSETU_DB", str(tmp_path / "seed.db"))
    monkeypatch.setattr(sys, "argv", ["seed_demo.py"])   # the script parses argv on import
    module = _load("seed_demo")
    assert module.auth.council_code() == "SABHA-2026"


def test_dockerfile_only_seeds_when_explicitly_enabled():
    """The container must not switch the demo on by itself."""
    cmd = (SCRIPTS.parent / "Dockerfile").read_text().splitlines()[-1]
    # The CMD is a JSON array, so the shell test arrives backslash-escaped.
    assert 'SAHAKARSETU_SEED_DEMO\\" = \\"1\\"' in cmd
    # ...and must refuse to seed without a password of its own.
    assert 'SAHAKARSETU_DEMO_PASSWORD\\" ]; then' in cmd
    assert "scripts/seed_demo.py" in cmd
    assert "exec uvicorn" in cmd, "uvicorn must be exec'd so it becomes PID 1"
