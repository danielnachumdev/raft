#!/bin/sh
# Supervisor: ensure a passwd row for the host UID (OpenSSH/ssh-keygen), then
# drop privileges and run app + nginx auth edge on the published port.
set -eu

uid="${RAFT_HOST_UID:-0}"
gid="${RAFT_HOST_GID:-0}"
home="${RAFT_HOST_HOME:-/home/raft}"
docker_gid="${RAFT_DOCKER_GID:-}"

export HOME="$home"
export RAFT_SSH_DIR="${RAFT_SSH_DIR:-$home/.ssh}"

ensure_operator_identity() {
  if getent passwd "$uid" >/dev/null 2>&1; then
    return 0
  fi
  if ! getent group "$gid" >/dev/null 2>&1; then
    groupadd -g "$gid" raftop
  fi
  useradd -u "$uid" -g "$gid" -d "$home" -M -s /bin/sh raftop
}

ensure_docker_sock_group() {
  name="$(getent passwd "$uid" | cut -d: -f1)"
  if [ -z "$name" ] || [ -z "$docker_gid" ] || [ "$docker_gid" = "0" ]; then
    return 0
  fi
  if ! getent group "$docker_gid" >/dev/null 2>&1; then
    groupadd -g "$docker_gid" dockersock
  fi
  usermod -aG "$docker_gid" "$name" 2>/dev/null || true
}

if [ "$(id -u)" -eq 0 ] && [ "$uid" != "0" ]; then
  ensure_operator_identity
  ensure_docker_sock_group
  echo "dashboard: dropping to uid=${uid} gid=${gid} home=${home}"
  exec setpriv --reuid="$uid" --regid="$gid" --init-groups -- "$0" "$@"
fi

echo "dashboard: writing nginx.conf + starting app (uid=$(id -u))"
python -m raft.services.dashboard
# DashboardProcess runs nginx in the foreground and exits when either dies.
