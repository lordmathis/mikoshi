from mikoshi.skills.registry import SkillRegistry


def _make_registry(tmp_path, frontmatter=""):
    skill_dir = tmp_path / "my-skill"
    skill_dir.mkdir()
    (skill_dir / "SKILL.md").write_text(f"---\n{frontmatter}---\nbody\n")
    return SkillRegistry(str(tmp_path))


class TestSkillSerialization:
    def test_to_dict_excludes_disk_path(self, tmp_path):
        registry = _make_registry(tmp_path)
        data = registry.list_skills()[0]
        assert "path" not in data
        assert data["name"] == "my-skill"
        assert data["exists"] is True
        assert data["required_tool_servers"] == []

    def test_required_tool_servers_parsed(self, tmp_path):
        registry = _make_registry(tmp_path, "required_tool_servers: [gitea]\n")
        assert registry.list_skills()[0]["required_tool_servers"] == ["gitea"]
