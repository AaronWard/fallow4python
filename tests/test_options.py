"""Tests for option parsing and per-command presets."""
from __future__ import annotations

from fallow4python.options import args_to_options, build_arg_parser


def _opts(argv):
    return args_to_options(build_arg_parser().parse_args(argv))


def test_defaults():
    o = _opts([])
    assert o.command == "scan" and o.target == "." and o.fmt == "human"
    assert o.run_tests is True and o.tools is None


def test_health_command_preset():
    o = _opts(["health", "src"])
    assert o.tools == {"radon-cc", "radon-mi", "xenon", "duplication"}


def test_audit_sets_base():
    o = _opts(["audit", "."])
    assert o.base == "origin/main"


def test_explicit_tools_override_preset():
    o = _opts(["health", ".", "--tools", "ruff, mypy"])
    assert o.tools == {"ruff", "mypy"}


def test_explicit_inputs_and_flags():
    o = _opts(["scan", ".", "--ruff", "r.json", "--ignore-tests",
               "--format", "json", "--no-run"])
    assert o.explicit_inputs["ruff"] == "r.json"
    assert o.run_tests is False and o.fmt == "json" and o.no_run is True
