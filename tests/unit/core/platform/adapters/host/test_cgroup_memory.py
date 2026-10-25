"""Cgroup / self RSS helpers for controller memory budgets."""

from pathlib import Path

from raft.core.platform.adapters.host.cgroup_memory import CgroupMemory


class TestCgroupMemory:
    def test_usage_ratio_from_scoped_cgroup(self, tmp_path: Path) -> None:
        scope = tmp_path / "docker-demo.scope"
        scope.mkdir()
        (scope / "memory.current").write_text("75\n", encoding="utf-8")
        (scope / "memory.max").write_text("100\n", encoding="utf-8")
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "cgroup").write_text("0::/docker-demo.scope\n", encoding="utf-8")
        mem = CgroupMemory(cgroup_root=tmp_path, proc_self=proc)
        assert mem.usage_ratio() == 0.75
        assert mem.elevated(threshold=0.75) is True
        assert mem.elevated(threshold=0.8) is False

    def test_unlimited_max_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "memory.current").write_text("10\n", encoding="utf-8")
        (tmp_path / "memory.max").write_text("max\n", encoding="utf-8")
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "cgroup").write_text("0::/\n", encoding="utf-8")
        assert CgroupMemory(cgroup_root=tmp_path, proc_self=proc).usage_ratio() is None

    def test_non_digit_max_returns_none(self, tmp_path: Path) -> None:
        (tmp_path / "memory.current").write_text("10\n", encoding="utf-8")
        (tmp_path / "memory.max").write_text("nope\n", encoding="utf-8")
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "cgroup").write_text("0::/\n", encoding="utf-8")
        assert CgroupMemory(cgroup_root=tmp_path, proc_self=proc).usage_ratio() is None

    def test_missing_cgroup_file_falls_back_to_root(self, tmp_path: Path) -> None:
        (tmp_path / "memory.current").write_text("40\n", encoding="utf-8")
        (tmp_path / "memory.max").write_text("80\n", encoding="utf-8")
        proc = tmp_path / "proc"
        proc.mkdir()
        # No :: line → relative path None → root files.
        (proc / "cgroup").write_text("1:name=systemd:/\n", encoding="utf-8")
        assert CgroupMemory(cgroup_root=tmp_path, proc_self=proc).usage_ratio() == 0.5

    def test_missing_scoped_files_fall_back_to_root(self, tmp_path: Path) -> None:
        (tmp_path / "memory.current").write_text("20\n", encoding="utf-8")
        (tmp_path / "memory.max").write_text("40\n", encoding="utf-8")
        # Relative path points at a dir with no memory.* files.
        missing = tmp_path / "missing-scope"
        missing.mkdir()
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "cgroup").write_text("0::/missing-scope\n", encoding="utf-8")
        assert CgroupMemory(cgroup_root=tmp_path, proc_self=proc).usage_ratio() == 0.5

    def test_rss_skips_non_vmrss_lines(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "status").write_text(
            "Name:\tpython\nVmSize:\t9999 kB\nVmRSS:\t512 kB\n",
            encoding="utf-8",
        )
        assert CgroupMemory(proc_self=proc).rss_bytes() == 512 * 1024

    def test_rss_skips_malformed_vmrss_then_parses(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "status").write_text(
            "VmRSS:\nVmRSS:\tnotadigit kB\nVmRSS:\t256 kB\n",
            encoding="utf-8",
        )
        assert CgroupMemory(proc_self=proc).rss_bytes() == 256 * 1024

    def test_rss_bytes(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "status").write_text("Name:\tpython\nVmRSS:\t2048 kB\n", encoding="utf-8")
        assert CgroupMemory(proc_self=proc).rss_bytes() == 2048 * 1024

    def test_rss_missing_status(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        assert CgroupMemory(proc_self=proc).rss_bytes() is None

    def test_rss_without_vmrss_line(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "status").write_text("Name:\tpython\n", encoding="utf-8")
        assert CgroupMemory(proc_self=proc).rss_bytes() is None

    def test_non_digit_current(self, tmp_path: Path) -> None:
        (tmp_path / "memory.current").write_text("x\n", encoding="utf-8")
        (tmp_path / "memory.max").write_text("100\n", encoding="utf-8")
        proc = tmp_path / "proc"
        proc.mkdir()
        (proc / "cgroup").write_text("0::/\n", encoding="utf-8")
        assert CgroupMemory(cgroup_root=tmp_path, proc_self=proc).usage_ratio() is None

    def test_elevated_false_when_ratio_unknown(self, tmp_path: Path) -> None:
        proc = tmp_path / "proc"
        proc.mkdir()
        assert CgroupMemory(cgroup_root=tmp_path, proc_self=proc).elevated() is False
