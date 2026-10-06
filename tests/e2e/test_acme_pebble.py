"""E2E: tls: acme against Let's Encrypt Pebble (issue / scale-to-zero / renew)."""

from __future__ import annotations

import pytest

from tests.e2e.shared.acme_stack import AcmeE2EStack

pytestmark = pytest.mark.e2e


class TestE2EAcmePebble:
    def test_issue_and_https(self, isolated_raft_env) -> None:
        with AcmeE2EStack.create(isolated_raft_env) as stack:
            stack.ensure_acme()
            stack.assert_https_ok()

    def test_http01_while_scaled_to_zero(self, isolated_raft_env) -> None:
        with AcmeE2EStack.create(isolated_raft_env) as stack:
            stack.scale_to_zero()
            stack.assert_challenge_token("e2e-token", "e2e-key-authorization")
            stack.ensure_acme()
            stack.assert_https_ok()

    def test_renew_reloads_https(self, isolated_raft_env) -> None:
        with AcmeE2EStack.create(isolated_raft_env) as stack:
            stack.ensure_acme()
            before = stack.pem_digest()
            stack.force_renew_window()
            stack.ensure_acme()
            assert stack.pem_digest() != before
            stack.assert_https_ok()
