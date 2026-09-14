"""Skill registry for discovering and managing skills."""

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

logger = logging.getLogger(__name__)


class Skill:
    """Represents a skill with its metadata."""

    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path
        self.skill_file = path / "SKILL.md"
        self._frontmatter: Optional[Dict[str, Any]] = None
        self._content: Optional[str] = None
        self._parse_skill_file()

    @property
    def exists(self) -> bool:
        """Check if the SKILL.md file exists."""
        return self.skill_file.exists()

    def _parse_skill_file(self) -> None:
        """Parse the SKILL.md file to extract frontmatter and content."""
        if not self.exists:
            self._frontmatter = {}
            self._content = ""
            return

        try:
            raw_content = self.skill_file.read_text(encoding="utf-8")

            frontmatter_pattern = r"^---\s*\n(.*?)\n---\s*\n(.*)$"
            match = re.match(frontmatter_pattern, raw_content, re.DOTALL)

            if not match:
                self._frontmatter = {}
                self._content = raw_content
                return

            frontmatter_text = match.group(1)
            self._content = match.group(2)
            try:
                self._frontmatter = yaml.safe_load(frontmatter_text) or {}
            except yaml.YAMLError as e:
                logger.warning(
                    f"Failed to parse frontmatter for skill {self.name}: {e}"
                )
                self._frontmatter = {}

        except Exception as e:
            logger.error(f"Error reading skill file {self.skill_file}: {e}")
            self._frontmatter = {}
            self._content = ""

    def read_content(self) -> str:
        """Read the content of the SKILL.md file on demand."""
        if not self.exists:
            raise FileNotFoundError(f"SKILL.md not found for skill: {self.name}")
        return self._content or ""

    def get_required_tool_servers(self) -> List[str]:
        """Get the list of required tool servers from frontmatter."""
        if not self._frontmatter:
            return []

        required = self._frontmatter.get("required_tool_servers", [])
        if isinstance(required, list):
            return required
        elif isinstance(required, str):
            return [required]
        else:
            return []

    def to_dict(self) -> Dict[str, Any]:
        """Convert skill to dictionary representation.

        Deliberately excludes the on-disk path: it's a server-internal
        detail that would leak filesystem layout to API clients.
        """
        return {
            "name": self.name,
            "exists": self.exists,
            "required_tool_servers": self.get_required_tool_servers(),
        }


class SkillRegistry:
    """Registry for discovering and managing skills."""

    def __init__(self, skills_dir: str):
        self.skills_dir = Path(skills_dir)
        self._skills: Dict[str, Skill] = {}
        self._discover_skills()

    def _discover_skills(self):
        """Discover all skills in the skills directory."""
        if not self.skills_dir.exists():
            logger.warning(f"Skills directory does not exist: {self.skills_dir}")
            return

        if not self.skills_dir.is_dir():
            logger.warning(f"Skills path is not a directory: {self.skills_dir}")
            return

        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue

            # Skip private/hidden directories
            if skill_dir.name.startswith("_") or skill_dir.name.startswith("."):
                continue

            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill_name = skill_dir.name
                skill = Skill(name=skill_name, path=skill_dir)
                self._skills[skill_name] = skill
                logger.info(f"Discovered skill: {skill_name}")

        logger.info(f"Discovered {len(self._skills)} skill(s)")

    def list_skills(self) -> List[Dict[str, Any]]:
        """List all available skills."""
        return [skill.to_dict() for skill in self._skills.values()]

    def get_skill(self, name: str) -> Skill | None:
        """Get a specific skill by name."""
        return self._skills.get(name)

    def get_skill_content(self, name: str) -> str | None:
        """Read the content of a specific skill."""
        skill = self.get_skill(name)
        if skill is None:
            return None
        try:
            return skill.read_content()
        except FileNotFoundError:
            logger.error(f"SKILL.md not found for skill: {name}")
            return None
