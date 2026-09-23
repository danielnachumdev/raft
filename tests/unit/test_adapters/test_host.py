"""Host resource adapter + docker size parsers."""

from __future__ import annotations

from pathlib import Path

from raft.adapters.host import (
    collect_host_resources,
    parse_docker_pair,
    parse_docker_size,
    parse_percent,
)


class TestParseDockerSize:
    def test_units(self) -> None:
        assert parse_docker_size("0") == 0
        assert parse_docker_size("1024B") == 1024
        assert parse_docker_size("1.5KiB") == int(1.5 * 1024)
        assert parse_docker_size("2MiB") == 2 * 1024**2
        assert parse_docker_size("1GiB") == 1024**3
        assert parse_docker_size("1MB") == 1000**2
        assert parse_docker_size("--") is None
        assert parse_docker_size("") is None
        assert parse_docker_size("not-a-size") is None
        assert parse_docker_size("1.2xB") is None

    def test_pair_and_percent(self) -> None:
        assert parse_docker_pair("1.5MiB / 64MiB") == (
            int(1.5 * 1024**2),
            64 * 1024**2,
        )
        assert parse_docker_pair("1KiB") == (1024, None)
        assert parse_percent("12.5%") == 12.5
        assert parse_percent("--") is None
        assert parse_percent("nope") is None


class TestCollectHostResources:
    def test_reads_proc_fixture(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "meminfo").write_text(
            "MemTotal:       2048000 kB\n"
            "MemAvailable:   1024000 kB\n"
            "MemFree:         512000 kB\n",
            encoding="utf-8",
        )
        (proc / "loadavg").write_text("0.10 0.20 0.30 1/100 1\n", encoding="utf-8")
        (proc / "uptime").write_text("3661.5 100.0\n", encoding="utf-8")
        disk_root = tmp_path / "disk"
        disk_root.mkdir()
        host = collect_host_resources(disk_path=disk_root, proc=proc)
        assert host.cpus is not None and host.cpus >= 1
        assert host.loadavg == (0.10, 0.20, 0.30)
        assert host.uptime_seconds == 3661.5
        assert host.memory is not None
        assert host.memory.total_bytes == 2048000 * 1024
        assert host.memory.available_bytes == 1024000 * 1024
        assert host.memory.used_bytes == host.memory.total_bytes - host.memory.available_bytes
        assert host.disk is not None
        assert host.disk.path == str(disk_root)
        assert host.disk.total_bytes > 0

    def test_missing_proc_degrades(self, tmp_path: Path) -> None:
        proc = tmp_path / "missing-proc"
        host = collect_host_resources(disk_path=tmp_path, proc=proc)
        assert host.loadavg is None
        assert host.memory is None
        assert host.uptime_seconds is None
        assert host.disk is not None

    def test_bad_meminfo_and_load(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "meminfo").write_text("Garbage line\nMemTotal: nope\n", encoding="utf-8")
        (proc / "loadavg").write_text("x y\n", encoding="utf-8")
        (proc / "uptime").write_text("nope\n", encoding="utf-8")
        host = collect_host_resources(disk_path=tmp_path, proc=proc)
        assert host.memory is None
        assert host.loadavg is None
        assert host.uptime_seconds is None

    def test_loadavg_value_error_and_empty_uptime(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "loadavg").write_text("a b c\n", encoding="utf-8")
        (proc / "uptime").write_text("\n", encoding="utf-8")
        (proc / "meminfo").write_text("MemTotal: 1000 kB\n", encoding="utf-8")
        host = collect_host_resources(disk_path=tmp_path, proc=proc)
        assert host.loadavg is None
        assert host.uptime_seconds is None
        assert host.memory is None  # MemAvailable missing

    def test_disk_errors(self, tmp_path: Path, monkeypatch) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "meminfo").write_text("", encoding="utf-8")

        def boom(_path):
            raise OSError("nope")

        monkeypatch.setattr("raft.adapters.host.shutil.disk_usage", boom)
        host = collect_host_resources(disk_path=tmp_path, proc=proc)
        assert host.disk is None

        class Zero:
            total = 0
            free = 0

        monkeypatch.setattr(
            "raft.adapters.host.shutil.disk_usage", lambda _p: Zero()
        )
        assert collect_host_resources(disk_path=tmp_path, proc=proc).disk is None

    def test_more_size_units(self) -> None:
        assert parse_docker_size("1TiB") == 1024**4
        assert parse_docker_size("1TB") == 1000**4
        assert parse_docker_size("1.5") == 1
        assert parse_docker_size("1KiBx") is None
