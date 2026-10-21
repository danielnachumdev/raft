"""Default image for host-targeted Docker one-shots (Update / self-Redeploy)."""

# curl + bash + git (install.sh always calls ensure_git); override with
# ``RAFT_HOST_UPDATE_IMAGE``. bookworm-curl lacks git and fails Update apply.
DEFAULT_HOST_ONESHOT_IMAGE = "docker.io/library/buildpack-deps:bookworm-scm"
