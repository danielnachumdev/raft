"""Unit tests for label-driven release semver helper."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_SCRIPT = _ROOT / "scripts" / "release_semver.py"


def _load():
    spec = importlib.util.spec_from_file_location("release_semver", _SCRIPT)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    sys.modules["release_semver"] = mod
    spec.loader.exec_module(mod)
    return mod


rs = _load()


class TestParseAndFormat:
    def test_parse_v_prefix(self):
        assert rs.parse_version("v1.2.3") == (1, 2, 3)

    def test_parse_bare(self):
        assert rs.parse_version("0.0.0") == (0, 0, 0)

    def test_parse_refs_tags(self):
        assert rs.parse_version("refs/tags/v9.0.1") == (9, 0, 1)

    def test_parse_rejects_garbage(self):
        with pytest.raises(ValueError, match="unsupported"):
            rs.parse_version("latest")

    def test_format_tag(self):
        assert rs.format_tag(1, 0, 0) == "v1.0.0"


class TestResolveAction:
    def test_each_bump(self):
        assert rs.resolve_action(["bumpMajor"]) == "major"
        assert rs.resolve_action(["bumpMinor", "enhancement"]) == "minor"
        assert rs.resolve_action(["documentation", "bumpPatch"]) == "patch"
        assert rs.resolve_action(["noBump"]) == "none"

    def test_missing_fails(self):
        with pytest.raises(rs.LabelError, match="missing release label"):
            rs.resolve_action(["enhancement"])

    def test_multiple_fails_closed(self):
        with pytest.raises(rs.LabelError, match="multiple"):
            rs.resolve_action(["bumpPatch", "noBump"])

    def test_two_bumps_fail(self):
        with pytest.raises(rs.LabelError, match="multiple"):
            rs.resolve_action(["bumpMajor", "bumpMinor"])


class TestNextTag:
    def test_first_release_patch(self):
        assert rs.next_tag("", ["bumpPatch"]) == "v0.0.1"

    def test_first_release_minor(self):
        assert rs.next_tag("", ["bumpMinor"]) == "v0.1.0"

    def test_bump_from_latest(self):
        assert rs.next_tag("v1.4.2", ["bumpMinor"]) == "v1.5.0"
        assert rs.next_tag("v1.4.2", ["bumpMajor"]) == "v2.0.0"
        assert rs.next_tag("v1.4.2", ["bumpPatch"]) == "v1.4.3"

    def test_nobump_returns_none(self):
        assert rs.next_tag("v1.0.0", ["noBump"]) is None


class TestMainCli:
    def test_outputs_skip(self, capsys):
        assert rs.main(["--latest-tag", "v1.0.0", "--label", "noBump"]) == 0
        out = capsys.readouterr().out
        assert "skip=true" in out
        assert "action=none" in out

    def test_outputs_tag(self, capsys):
        assert rs.main(["--latest-tag", "v0.1.0", "--label", "bumpPatch"]) == 0
        out = capsys.readouterr().out
        assert "tag=v0.1.1" in out
        assert "version=0.1.1" in out

    def test_labels_json_objects(self, capsys):
        payload = '[{"name":"bumpMinor"},{"name":"enhancement"}]'
        assert rs.main(["--latest-tag", "v1.0.0", "--labels-json", payload]) == 0
        assert "tag=v1.1.0" in capsys.readouterr().out

    def test_error_exit(self, capsys):
        assert rs.main(["--latest-tag", "v1.0.0"]) == 1
        assert "missing release label" in capsys.readouterr().err
