"""
skill_runner.py — skill loading and injection engine.

Skills are pure markdown folders. Each skill has:
  SKILL.md      — instructions injected as read-only context into Aider
  template.md   — optional output template
  checklist.md  — optional checklist

SkillRunner.resolve(skill_names) -> list[Path]
  Returns markdown files to pass as --read to Aider.

Resolution order (framework skill shadows global skill of same name):
  1. frameworks/<fw>/skills/<name>/
  2. skills/<name>/
"""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

SKILLS_DIR     = Path(__file__).parent.parent / "skills"
FRAMEWORKS_DIR = Path(__file__).parent.parent / "frameworks"


class SkillRunner:

    def __init__(self, framework_id: Optional[str] = None):
        self.framework_id = framework_id
        self._cache: dict[str, list[Path]] = {}

    def resolve(self, skill_names: list[str]) -> list[Path]:
        """Resolve skill names to a deduplicated list of markdown file paths."""
        files: list[Path] = []
        seen: set[Path] = set()
        for name in skill_names:
            for f in self._skill_files(name):
                if f not in seen:
                    files.append(f)
                    seen.add(f)
        if files:
            logger.debug("[skills] resolved %d files for: %s", len(files), skill_names)
        return files

    def _skill_files(self, skill_name: str) -> list[Path]:
        if skill_name in self._cache:
            return self._cache[skill_name]
        skill_dir = self._find_skill_dir(skill_name)
        if skill_dir is None:
            logger.warning("[skills] skill not found: '%s'", skill_name)
            return []
        files: list[Path] = []
        primary = skill_dir / "SKILL.md"
        if primary.exists():
            files.append(primary)
        for f in sorted(skill_dir.glob("*.md")):
            if f not in files:
                files.append(f)
        self._cache[skill_name] = files
        return files

    def _find_skill_dir(self, name: str) -> Optional[Path]:
        if self.framework_id:
            fw = FRAMEWORKS_DIR / self.framework_id / "skills" / name
            if fw.is_dir():
                return fw
        g = SKILLS_DIR / name
        return g if g.is_dir() else None

    def list_available(self) -> list[str]:
        names: set[str] = set()
        if SKILLS_DIR.exists():
            names.update(d.name for d in SKILLS_DIR.iterdir() if d.is_dir())
        if self.framework_id:
            fw_skills = FRAMEWORKS_DIR / self.framework_id / "skills"
            if fw_skills.exists():
                names.update(d.name for d in fw_skills.iterdir() if d.is_dir())
        return sorted(names)
