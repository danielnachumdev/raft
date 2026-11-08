"""DirectUrl parser coverage for path / VCS installs."""

from pathlib import Path

from raft.core.observe.ops.version.direct_url import DirectUrl


class TestDirectUrl:
    def test_local_path_none_for_vcs_info(self) -> None:
        data = {
            "url": "https://github.com/danielnachumdev/raft.git",
            "vcs_info": {"vcs": "git", "commit_id": "abc"},
        }
        assert DirectUrl().local_path(data) is None

    def test_local_path_from_dir_info(self) -> None:
        data = {
            "url": "file:///home/demo/dev/projects/raft",
            "dir_info": {"editable": True},
        }
        assert DirectUrl().local_path(data) == "/home/demo/dev/projects/raft"

    def test_from_dist_info_missing(self, tmp_path: Path) -> None:
        assert DirectUrl().from_dist_info(tmp_path) is None
