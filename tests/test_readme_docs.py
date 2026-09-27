from __future__ import annotations

import json
from pathlib import Path

from scripts.validate_readme_docs import REQUIRED_HEADINGS, check


def test_contract_required_readme_reference_must_be_linked(tmp_path: Path) -> None:
    (tmp_path / ".content-system").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "PRIOR_WORK.md").write_text("# Prior work\n", encoding="utf-8")
    (tmp_path / ".content-system" / "readme-contract.json").write_text(
        json.dumps({"required_references": ["docs/PRIOR_WORK.md"]}),
        encoding="utf-8",
    )
    headings = "\n".join(f"## {heading}" for heading in REQUIRED_HEADINGS)
    (tmp_path / "README.md").write_text(headings, encoding="utf-8")

    errors = check(tmp_path)

    assert "README does not link to contract-required reference: docs/PRIOR_WORK.md" in errors

    (tmp_path / "README.md").write_text(
        f"{headings}\n\n[Prior work](docs/PRIOR_WORK.md)\n", encoding="utf-8"
    )

    assert check(tmp_path) == []
