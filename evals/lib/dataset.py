"""Load and filter the evals dataset, and read skill content."""

import hashlib
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DATASET_PATH = REPO_ROOT / "evals" / "dataset.yaml"
TRIGGER_DATASET_PATH = REPO_ROOT / "evals" / "trigger_dataset.yaml"
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


def load_skill(skill_name: str) -> tuple[str, str, str]:
    """Load a skill's content for single-shot eval prompts.

    Returns (frontmatter_description, full_content, references_content).

    full_content is the entire SKILL.md file (including frontmatter).
    references_content is every .md file under references/ concatenated with
    path-labelled delimiters, or "" if the directory is absent or empty. Eval
    runs are single-shot, so bundling references here stands in for the
    progressive-disclosure reads a real agent would do across turns.
    """
    skill_dir = SKILLS_DIR / skill_name
    skill_path = skill_dir / "SKILL.md"
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

    references_content = _load_references(skill_dir)

    return description, full_content, references_content


def _load_references(skill_dir: Path) -> str:
    """Concatenate every .md file under references/ with path-labelled delimiters."""
    references_dir = skill_dir / "references"
    if not references_dir.is_dir():
        return ""

    chunks = []
    for md_path in sorted(references_dir.rglob("*.md")):
        rel = md_path.relative_to(skill_dir)
        chunks.append(f"## Reference: {rel.as_posix()}\n\n{md_path.read_text()}")

    return "\n\n".join(chunks)


def skill_path(skill_name: str) -> Path:
    """Return the path to a skill's SKILL.md."""
    return SKILLS_DIR / skill_name / "SKILL.md"


# --- Trigger eval functions ---


def load_trigger_dataset(path: Path = TRIGGER_DATASET_PATH) -> list[dict]:
    """Load trigger evals from trigger_dataset.yaml."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return data.get("trigger_evals", [])


def load_all_skill_descriptions() -> dict[str, str]:
    """Load name->description mapping for all skills with SKILL.md files.

    Returns dict like {"buildkite-pipelines": "This skill should be used when..."}
    Only includes skills that have a non-empty description in frontmatter.
    """
    descriptions = {}
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_md = skill_dir / "SKILL.md"
        if skill_md.exists():
            description, _, _ = load_skill(skill_dir.name)
            if description:
                descriptions[skill_dir.name] = description
    return descriptions


def filter_trigger_evals(
    evals: list[dict],
    skill: str | None = None,
    tags: list[str] | None = None,
    ids: list[str] | None = None,
    holdout: bool = False,
    holdout_ratio: float = 0.4,
) -> list[dict]:
    """Filter trigger evals by criteria. All filters are AND-ed together."""
    result = evals

    if skill:
        result = [e for e in result if e.get("expected_skill") == skill]

    if tags:
        result = [
            e for e in result
            if any(t in e.get("tags", []) for t in tags)
        ]

    if ids:
        id_set = set(ids)
        result = [e for e in result if e.get("id") in id_set]

    if holdout:
        result = [e for e in result if _is_holdout(e["id"], holdout_ratio)]

    return result
