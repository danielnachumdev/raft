"""SettingsRedactor coverage."""

from raft.core.observe.notify.settings_redactor import SettingsRedactor

from tests.unit.base import RaftTestCase


class TestSettingsRedactor(RaftTestCase):
    def test_masks_secret_keys_and_nested(self) -> None:
        out = SettingsRedactor().redact(
            {
                "to": "ops@example.com",
                "token": "super-secret",
                "clientSecret": "x",
                "nested": {"password": "p", "label": "ok"},
            }
        )
        assert out["to"] == "ops@example.com"
        assert out["token"] == "***"
        assert out["clientSecret"] == "***"
        assert out["nested"] == {"password": "***", "label": "ok"}

    def test_redacts_url_query_secrets(self) -> None:
        url = "https://hooks.example.invalid/raft?token=abc&ref=demo"
        out = SettingsRedactor().redact({"url": url})["url"]
        assert out == (
            "https://hooks.example.invalid/raft?token=%2A%2A%2A&ref=demo"
        )

    def test_url_without_query_unchanged(self) -> None:
        url = "https://hooks.example.invalid/raft"
        assert SettingsRedactor().redact({"url": url})["url"] == url

    def test_empty_secret_unchanged(self) -> None:
        assert SettingsRedactor().redact({"token": ""})["token"] == ""
        assert SettingsRedactor().redact({"token": None})["token"] is None

    def test_merge_preserving_secrets(self) -> None:
        redactor = SettingsRedactor()
        merged = redactor.merge_preserving_secrets(
            {"token": "keep", "label": "old", "nested": {"password": "p1"}},
            {"token": "***", "label": "new", "nested": {"password": "***", "x": 1}},
        )
        assert merged == {
            "token": "keep",
            "label": "new",
            "nested": {"password": "p1", "x": 1},
        }

    def test_masks_api_token_instance(self) -> None:
        out = SettingsRedactor().redact(
            {"apiTokenInstance": "demo-token-not-real", "chatId": "79001234567@c.us"}
        )
        assert out["apiTokenInstance"] == "***"
        assert out["chatId"] == "79001234567@c.us"
