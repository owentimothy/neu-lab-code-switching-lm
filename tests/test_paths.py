from cslm.utils.paths import project_root


def test_project_root_resolves():
    root = project_root()
    assert root.is_dir()
    assert (root / "pyproject.toml").exists()


def test_project_root_top_level_folders_exist():
    root = project_root()
    expected = ["src", "configs", "data", "notebooks", "scripts", "tests", "outputs"]
    for name in expected:
        assert (root / name).is_dir(), f"missing top-level folder: {name}"
