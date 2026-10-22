#!/usr/bin/env python3
"""Temporarily patch local hosts files for applied raft apps, then restore."""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
from typing import Optional

from hosts_plan import (
    DEFAULT_LINUX_HOSTS,
    DEFAULT_WINDOWS_HOSTS,
    HostsPlan,
)
from hosts_session import Hosts

def _cmd_hold(session: Hosts) -> int:
    print("Press Ctrl+C to restore both hosts files and exit.", flush=True)
    with session:
        for line in session.plan.describe():
            print(f"  {line}", flush=True)
        try:
            signal.pause()
        except KeyboardInterrupt:
            print("\nInterrupted — restoring hosts.", flush=True)
    print("hosts restored.", flush=True)
    return 0


def _cmd_run(session: Hosts, command: list[str]) -> int:
    if not command:
        raise SystemExit("run requires a command after --")
    with session:
        print(f"hosts patched for duration of: {' '.join(command)}", flush=True)
        completed = subprocess.run(command, check=False)
        return completed.returncode


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Safely patch Linux /etc/hosts and the Windows hosts file for "
            "applied raft publicHost values, then always restore prior state."
        )
    )
    parser.add_argument(
        "--linux-hosts",
        default=str(DEFAULT_LINUX_HOSTS),
        help="Linux hosts path (default: /etc/hosts)",
    )
    parser.add_argument(
        "--windows-hosts",
        default=str(DEFAULT_WINDOWS_HOSTS),
        help="Windows hosts path as seen from WSL",
    )
    parser.add_argument(
        "--linux-only",
        action="store_true",
        help="only patch Linux /etc/hosts",
    )
    parser.add_argument(
        "--windows-only",
        action="store_true",
        help="only patch the Windows hosts file",
    )
    parser.add_argument(
        "--no-flush-dns",
        action="store_true",
        help="skip ipconfig /flushdns after Windows changes",
    )
    parser.add_argument(
        "--entry",
        action="append",
        metavar="IP,name[,name...]",
        help="override HostsPlan.from_applied_apps(); repeatable",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("hold", help="apply entries until Ctrl+C / signal, then restore")
    run_parser = sub.add_parser("run", help="apply entries, run a command, restore afterward")
    run_parser.add_argument(
        "cmd",
        nargs=argparse.REMAINDER,
        help="command to run (use -- before it)",
    )

    args = parser.parse_args(argv)
    if args.linux_only and args.windows_only:
        parser.error("use only one of --linux-only / --windows-only")

    session = Hosts(
        plan=HostsPlan.from_cli_entries(args.entry),
        linux_hosts=args.linux_hosts,
        windows_hosts=args.windows_hosts,
        include_linux=not args.windows_only,
        include_windows=not args.linux_only,
        flush_windows_dns=not args.no_flush_dns,
    )

    if args.command == "hold":
        return _cmd_hold(session)
    if args.command == "run":
        cmd = list(args.cmd)
        if cmd and cmd[0] == "--":
            cmd = cmd[1:]
        return _cmd_run(session, cmd)
    parser.error(f"unknown command {args.command}")
    return 2


if __name__ == "__main__":
    sys.exit(main())
