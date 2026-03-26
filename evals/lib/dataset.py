"""Load and filter the evals dataset, and read skill content."""

import hashlib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = REPO_ROOT / "evals" / "dataset.yaml"
SKILLS_DIR = REPO_ROOT / "skills"


def load_dataset(path: Path = DATASET_PATH) -> list[dict]:
    """Load evals from dataset.yaml, returning list of eval dicts."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("evals", [])


def filter_evals(
    evals: list[dict],
    skill: str | None = None,
    cluster: str | None = None,
    tags: list[str] | None = None,
    difficulty: str | None = None,
    ids: list[str] | None = None,
    holdout: bool = False,
    holdout_ratio: float = 0.2,
) -> list[dict]:
    """Filter evals by various criteria. All filters are AND-ed together."""
    result = evals

    if skill:
        result = [e for e in result if e.get("primary_skill") == skill]

    if cluster:
        result = [e for e in result if e.get("cluster") == cluster]

    if tags:
        result = [
            e for e in result
            if any(t in e.get("tags", []) for t in tags)
        ]

    if difficulty:
        result = [e for e in result if e.get("difficulty") == difficulty]

    if ids:
        id_set = set(ids)
        result = [e for e in result if e.get("id") in id_set]

    if holdout:
        result = [e for e in result if _is_holdout(e["id"], holdout_ratio)]

    return result


def _is_holdout(eval_id: str, ratio: float) -> bool:
    """Deterministic holdout split based on hash of eval ID."""
    h = hashlib.md5(eval_id.encode()).hexdigest()
    return (int(h, 16) % 100) < (ratio * 100)


def load_skill(skill_name: str) -> tuple[str, str]:
    """Load a skill's SKILL.md, returning (frontmatter_description, full_content).

    The full_content includes frontmatter — it's the entire file as the model
    would see it when the skill is loaded.
    """
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_path.exists():
        raise FileNotFoundError(f"Skill not found: {skill_path}")

    full_content = skill_path.read_text()

    # Extract description from YAML frontmatter
    description = ""
    if full_content.startswith("---"):
        parts = full_content.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1])
            if fm and "description" in fm:
                description = fm["description"].strip()

    return description, full_content


def skill_path(skill_name: str) -> Path:
    """Return the path to a skill's SKILL.md."""
    return SKILLS_DIR / skill_name / "SKILL.md"
