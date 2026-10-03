"""E2E stories: dependsOn wake + parent idle co-stop."""

from __future__ import annotations

import pytest

from tests.e2e.shared.scale_depends_stack import ScaleDependsWakeStack

pytestmark = pytest.mark.e2e


class TestE2EScaleDependsWake:
    def test_wake_starts_backend_then_frontend(self, isolated_raft_env) -> None:
        with ScaleDependsWakeStack.create(isolated_raft_env) as site:
            site.given_frontend_and_backend_are_running()

            site.when_the_backend_is_stopped()
            site.and_the_frontend_is_scaled_to_zero()
            assert site.visitor_sees_the_holding_page()

            site.when_a_visitor_keeps_requesting_the_site()

            site.then_the_backend_is_running()
            site.then_the_frontend_is_running()
            site.then_the_site_serves_the_app()

    def test_idle_stop_costops_backend_then_wake(self, isolated_raft_env) -> None:
        with ScaleDependsWakeStack.create(isolated_raft_env) as site:
            site.given_frontend_and_backend_are_running()

            site.when_the_frontend_idle_stops()
            site.then_both_are_scaled_to_zero()
            assert site.visitor_sees_the_holding_page()

            site.when_a_visitor_keeps_requesting_the_site()

            site.then_the_backend_is_running()
            site.then_the_frontend_is_running()
            site.then_the_site_serves_the_app()
