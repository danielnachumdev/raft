"""Central operator error CTAs for raft.

Add a ``Rule`` in ``classify.SUBPROCESS_RULES`` or a factory in ``domain`` —
do not hand-build ``Fix:`` strings at call sites.
"""

from __future__ import annotations

from .certs_msgs import (
    format_missing_origin_certs,
    looks_like_missing_origin_cert,
    missing_origin_certs_fallback,
)
from .checked import (
    raise_for_compose_failure,
    raise_for_docker_pull_failure,
    raise_for_git_failure,
    run_checked,
    run_compose_checked,
    run_docker_checked,
)
from .classify import (
    SUBPROCESS_RULES,
    SubprocessCtx,
    classify_subprocess,
    generic_command_failed,
)
from .cta import OperatorError, first_line, format_cta, operator, subprocess_detail
from .docker_msgs import (
    compose_failure_message,
    docker_daemon_message,
    docker_failure_message,
    docker_pull_failure_message,
    looks_like_docker_daemon_down,
    looks_like_image_missing,
    looks_like_port_in_use,
    nginx_rejected,
    nginx_rejected_message,
    nginx_reload_failed,
    nginx_reload_failed_message,
    port_in_use_message,
)
from .domain import (
    app_not_applied,
    apply_requires_source,
    auth_requires_service,
    filesystem_error,
    invalid_yaml,
    missing_manifest,
    redeploy_requires_app,
    require_bool,
    require_int,
    require_mapping,
    service_not_running,
    unknown_app,
)
from .git_msgs import (
    git_auth_failure_message,
    git_generic_failure_message,
    git_network_failure_message,
    looks_like_git_auth_failure,
    looks_like_git_network_failure,
)
from .registry_msgs import (
    ghcr_pat_create_url,
    is_ghcr_image,
    looks_like_registry_unauthorized,
    missing_image_doctor_fix,
    registry_login_fix_steps,
    registry_unauthorized_message,
)

__all__ = [
    "OperatorError",
    "operator",
    "SUBPROCESS_RULES",
    "SubprocessCtx",
    "app_not_applied",
    "apply_requires_source",
    "auth_requires_service",
    "classify_subprocess",
    "compose_failure_message",
    "docker_daemon_message",
    "docker_failure_message",
    "docker_pull_failure_message",
    "filesystem_error",
    "first_line",
    "format_cta",
    "format_missing_origin_certs",
    "generic_command_failed",
    "ghcr_pat_create_url",
    "git_auth_failure_message",
    "git_generic_failure_message",
    "git_network_failure_message",
    "invalid_yaml",
    "is_ghcr_image",
    "looks_like_docker_daemon_down",
    "looks_like_git_auth_failure",
    "looks_like_git_network_failure",
    "looks_like_image_missing",
    "looks_like_missing_origin_cert",
    "looks_like_port_in_use",
    "looks_like_registry_unauthorized",
    "missing_image_doctor_fix",
    "missing_manifest",
    "missing_origin_certs_fallback",
    "nginx_rejected",
    "nginx_rejected_message",
    "nginx_reload_failed",
    "nginx_reload_failed_message",
    "port_in_use_message",
    "raise_for_compose_failure",
    "raise_for_docker_pull_failure",
    "raise_for_git_failure",
    "redeploy_requires_app",
    "registry_login_fix_steps",
    "registry_unauthorized_message",
    "require_bool",
    "require_int",
    "require_mapping",
    "run_checked",
    "run_compose_checked",
    "run_docker_checked",
    "service_not_running",
    "subprocess_detail",
    "unknown_app",
]
