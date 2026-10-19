"""Dump settings.yaml without YAML turning ``off``/``on`` into booleans."""

from typing import Any, Mapping

import yaml


class _QuotedStr(str):
    """Force a single-quoted YAML scalar for ambiguous tokens."""


def _represent_quoted(dumper: yaml.Dumper, data: _QuotedStr) -> Any:
    return dumper.represent_scalar("tag:yaml.org,2002:str", str(data), style="'")


yaml.add_representer(_QuotedStr, _represent_quoted, Dumper=yaml.SafeDumper)


class SettingsYamlDump:
    """``yaml.safe_dump`` with safe quoting for bool-like string tokens."""

    _AMBIGUOUS = frozenset(
        {
            "off",
            "on",
            "yes",
            "no",
            "true",
            "false",
            "null",
            "y",
            "n",
        }
    )

    def dump(self, data: Mapping[str, Any]) -> str:
        return yaml.safe_dump(self._quote(dict(data)), sort_keys=False)

    def _quote(self, value: Any) -> Any:
        if isinstance(value, dict):
            return {key: self._quote(item) for key, item in value.items()}
        if isinstance(value, list):
            return [self._quote(item) for item in value]
        if isinstance(value, str) and value.lower() in self._AMBIGUOUS:
            return _QuotedStr(value)
        return value
