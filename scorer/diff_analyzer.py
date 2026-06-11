"""Signal 1 — parse the PR diff via the GitHub API and tag changed files
against clinical_modules.json."""

import json
import os
from fnmatch import fnmatch
from typing import List, Tuple

import requests

from scorer.models import ChangedModule

GITHUB_API = "https://api.github.com"


def load_clinical_modules(config_path: str = "config/clinical_modules.json") -> dict:
    """Load and return the clinical modules configuration.

    Raises FileNotFoundError with a clear message if the config is missing —
    this is a required config file.
    """
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Required clinical modules config not found at '{config_path}'. "
            "This file maps file paths to clinical risk weights and is mandatory."
        )
    with open(config_path) as f:
        return json.load(f)


def tag_file(file_path: str, modules_config: dict) -> Tuple[str, int]:
    """Return (domain, risk_weight) for a given file path using fnmatch glob matching.

    If the file matches multiple patterns, the highest risk weight wins.
    If no pattern matches, returns ("Unclassified", default_risk_weight).
    """
    default_weight = modules_config.get("default_risk_weight", 2)
    best_domain = "Unclassified"
    best_weight = 0

    for module in modules_config.get("modules", []):
        pattern = module["pattern"]
        # fnmatch with ** does not behave like recursive globs natively, so we
        # also test against a normalised path and the basename.
        if _glob_match(file_path, pattern):
            if module["risk_weight"] > best_weight:
                best_weight = module["risk_weight"]
                best_domain = module["domain"]

    if best_weight == 0:
        return ("Unclassified", default_weight)
    return (best_domain, best_weight)


def _glob_match(file_path: str, pattern: str) -> bool:
    """Glob match that treats `**` as 'any number of path segments'."""
    # fnmatch treats * as matching path separators too, which is close enough
    # for `**/foo` style patterns. Normalise leading **/ so a top-level file
    # also matches (e.g. '**/vitals/**' should match 'vitals/x.py').
    if fnmatch(file_path, pattern):
        return True
    # Handle '**/' prefix matching zero leading directories.
    if pattern.startswith("**/"):
        if fnmatch(file_path, pattern[3:]):
            return True
    return False


def analyze_diff(
    token: str,
    repo: str,
    base_sha: str,
    head_sha: str,
    modules_config: dict,
) -> Tuple[List[str], List[ChangedModule], int]:
    """
    Returns:
        changed_files: all file paths changed in the PR
        clinical_modules_touched: files that matched a clinical module pattern
        max_risk_weight: highest risk weight among matched files
    """
    owner_repo = repo
    url = f"{GITHUB_API}/repos/{owner_repo}/compare/{base_sha}...{head_sha}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    changed_files: List[str] = []
    clinical_modules: List[ChangedModule] = []
    max_weight = 0

    for f in data.get("files", []):
        path = f["filename"]
        changed_files.append(path)
        domain, weight = tag_file(path, modules_config)
        max_weight = max(max_weight, weight)

        # Only count it as a "clinical module touched" if it matched a real
        # pattern (domain != Unclassified). Unclassified files still influence
        # max_weight via the default weight.
        if domain != "Unclassified":
            clinical_modules.append(
                ChangedModule(
                    file_path=path,
                    domain=domain,
                    risk_weight=weight,
                    lines_added=f.get("additions", 0),
                    lines_removed=f.get("deletions", 0),
                )
            )

    return changed_files, clinical_modules, max_weight
