
import pytest
from tests.conftest import FIXTURES, write_skill

from skill_lint.discover import PathError, discover


def test_discovers_skill_directory(tmp_path):
    skill = write_skill(tmp_path, "alpha")
    targets = discover([skill])
    assert len(targets) == 1
    assert targets[0].skill_dir == skill.resolve()
    assert targets[0].exact_filename is True


def test_discovers_skill_file(tmp_path):
    skill = write_skill(tmp_path, "alpha")
    targets = discover([skill / "SKILL.md"])
    assert len(targets) == 1


def test_discovers_project_skill_roots():
    targets = discover([FIXTURES / "project"])
    names = sorted(target.skill_dir.name for target in targets)
    assert names == ["commit-message", "ship-notes"]


def test_skips_node_modules(tmp_path):
    write_skill(tmp_path / "node_modules", "ignored-pkg")
    write_skill(tmp_path, "kept")
    targets = discover([tmp_path])
    assert [t.skill_dir.name for t in targets] == ["kept"]


def test_missing_path_raises(tmp_path):
    with pytest.raises(PathError, match="does not exist"):
        discover([tmp_path / "nope"])


def test_wrong_case_filename_is_still_found(tmp_path):
    write_skill(tmp_path, "alpha", filename="skill.md")
    targets = discover([tmp_path / "alpha"])
    assert len(targets) == 1
    assert targets[0].exact_filename is False
