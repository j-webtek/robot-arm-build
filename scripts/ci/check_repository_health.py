"""Read-only drift checks for Tactevra's GitHub repository configuration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from typing import Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / ".github/repository-health-policy.json"
SCHEMA = "tactevra.repository-health-policy.v1"
JsonFetcher = Callable[[str], object]
TextFetcher = Callable[[str], str]


def load_policy(path: Path = POLICY_PATH) -> tuple[dict[str, object] | None, list[str]]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [f"{path}: cannot read strict JSON: {exc}"]
    if not isinstance(value, dict):
        return None, [f"{path}: policy root must be an object"]
    errors: list[str] = []
    if value.get("schema") != SCHEMA:
        errors.append(f"{path}: unsupported schema")
    repository = value.get("repository")
    if not isinstance(repository, str) or not re.fullmatch(r"[^/\s]+/[^/\s]+", repository):
        errors.append(f"{path}: repository must be an owner/name string")
    for section in ("public", "owner"):
        if not isinstance(value.get(section), dict):
            errors.append(f"{path}: {section} must be an object")
    public = value.get("public", {})
    if isinstance(public, dict):
        if not isinstance(public.get("repository_fields"), dict):
            errors.append(f"{path}: public.repository_fields must be an object")
        workflows = public.get("required_workflows")
        if not isinstance(workflows, dict) or not workflows:
            errors.append(f"{path}: public.required_workflows must be a non-empty object")
        pages = public.get("pages")
        if not isinstance(pages, dict) or not str(pages.get("url", "")).startswith("https://"):
            errors.append(f"{path}: public.pages.url must be HTTPS")
    return value, errors


def compare_fields(observed: object, expected: object, label: str) -> list[str]:
    if not isinstance(observed, dict) or not isinstance(expected, dict):
        return [f"{label}: expected and observed values must be objects"]
    errors: list[str] = []
    for key, wanted in expected.items():
        actual = observed.get(key)
        if actual != wanted:
            errors.append(f"{label}.{key}: expected {wanted!r}, observed {actual!r}")
    return errors


def evaluate_public(
    policy: dict[str, object], fetch_json: JsonFetcher, fetch_text: TextFetcher
) -> tuple[list[str], list[tuple[str, str]]]:
    repository = str(policy["repository"])
    expected = policy["public"]
    assert isinstance(expected, dict)
    errors: list[str] = []
    rows: list[tuple[str, str]] = []

    repo = fetch_json(f"/repos/{repository}")
    errors.extend(compare_fields(repo, expected["repository_fields"], "repository"))
    rows.append(("Public repository metadata", "pass" if not errors else "drift"))

    branch = fetch_json(f"/repos/{repository}/branches/main")
    branch_errors = compare_fields(
        branch,
        {"protected": expected["default_branch_protected"]},
        "default branch",
    )
    errors.extend(branch_errors)
    rows.append(("Default branch protected", "pass" if not branch_errors else "drift"))

    community = fetch_json(f"/repos/{repository}/community/profile")
    minimum = expected["minimum_community_health_percentage"]
    health = community.get("health_percentage") if isinstance(community, dict) else None
    health_errors: list[str] = []
    if not isinstance(health, int) or health < minimum:
        health_errors.append(
            f"community health: expected at least {minimum}, observed {health!r}"
        )
    errors.extend(health_errors)
    rows.append(("Community profile", "pass" if not health_errors else "drift"))

    workflow_response = fetch_json(f"/repos/{repository}/actions/workflows")
    workflows = workflow_response.get("workflows", []) if isinstance(workflow_response, dict) else []
    observed_workflows = {
        item.get("path"): item.get("state") for item in workflows if isinstance(item, dict)
    }
    workflow_errors = compare_fields(
        observed_workflows, expected["required_workflows"], "required workflows"
    )
    errors.extend(workflow_errors)
    rows.append(("Required workflows active", "pass" if not workflow_errors else "drift"))

    pages = expected["pages"]
    assert isinstance(pages, dict)
    page_errors: list[str] = []
    body = fetch_text(str(pages["url"]))
    if str(pages["title_contains"]).casefold() not in body.casefold():
        page_errors.append(
            f"Pages title: expected content containing {pages['title_contains']!r}"
        )
    errors.extend(page_errors)
    rows.append(("Public Pages endpoint", "pass" if not page_errors else "drift"))
    return errors, rows


def evaluate_owner(policy: dict[str, object], fetch_json: JsonFetcher) -> tuple[list[str], list[tuple[str, str]]]:
    repository = str(policy["repository"])
    expected = policy["owner"]
    assert isinstance(expected, dict)
    errors: list[str] = []
    rows: list[tuple[str, str]] = []

    repo = fetch_json(f"/repos/{repository}")
    security = repo.get("security_and_analysis", {}) if isinstance(repo, dict) else {}
    observed_security = {
        key: value.get("status") if isinstance(value, dict) else None
        for key, value in security.items()
    } if isinstance(security, dict) else {}
    section_errors = compare_fields(
        observed_security, expected["security_and_analysis"], "security and analysis"
    )
    errors.extend(section_errors)
    rows.append(("Security settings", "pass" if not section_errors else "drift"))

    protection = fetch_json(f"/repos/{repository}/branches/main/protection")
    required = protection.get("required_status_checks", {}) if isinstance(protection, dict) else {}
    reviews = protection.get("required_pull_request_reviews", {}) if isinstance(protection, dict) else {}
    branch_observed = {
        "strict_status_checks": required.get("strict") if isinstance(required, dict) else None,
        "required_status_contexts": sorted(required.get("contexts", [])) if isinstance(required, dict) else [],
        "enforce_admins": _enabled(protection, "enforce_admins"),
        "dismiss_stale_reviews": reviews.get("dismiss_stale_reviews") if isinstance(reviews, dict) else None,
        "required_approving_review_count": reviews.get("required_approving_review_count") if isinstance(reviews, dict) else None,
        "required_linear_history": _enabled(protection, "required_linear_history"),
        "required_conversation_resolution": _enabled(protection, "required_conversation_resolution"),
        "allow_force_pushes": _enabled(protection, "allow_force_pushes"),
        "allow_deletions": _enabled(protection, "allow_deletions"),
    }
    branch_expected = dict(expected["branch_protection"])
    branch_expected["required_status_contexts"] = sorted(branch_expected["required_status_contexts"])
    section_errors = compare_fields(branch_observed, branch_expected, "branch protection")
    errors.extend(section_errors)
    rows.append(("Branch protection", "pass" if not section_errors else "drift"))

    actions = fetch_json(f"/repos/{repository}/actions/permissions")
    selected = fetch_json(f"/repos/{repository}/actions/permissions/selected-actions")
    workflow = fetch_json(f"/repos/{repository}/actions/permissions/workflow")
    action_observed = {}
    for source in (actions, selected, workflow):
        if isinstance(source, dict):
            action_observed.update(source)
    if isinstance(action_observed.get("patterns_allowed"), list):
        action_observed["patterns_allowed"] = sorted(action_observed["patterns_allowed"])
    action_expected = dict(expected["actions"])
    action_expected["patterns_allowed"] = sorted(action_expected["patterns_allowed"])
    section_errors = compare_fields(action_observed, action_expected, "Actions policy")
    errors.extend(section_errors)
    rows.append(("Actions policy", "pass" if not section_errors else "drift"))

    pages = fetch_json(f"/repos/{repository}/pages")
    page_observed = dict(pages) if isinstance(pages, dict) else {}
    source = page_observed.get("source", {})
    page_observed["source_branch"] = source.get("branch") if isinstance(source, dict) else None
    page_observed["source_path"] = source.get("path") if isinstance(source, dict) else None
    section_errors = compare_fields(page_observed, expected["pages"], "Pages settings")
    errors.extend(section_errors)
    rows.append(("Pages settings", "pass" if not section_errors else "drift"))
    return errors, rows


def _enabled(value: object, key: str) -> object:
    if not isinstance(value, dict):
        return None
    nested = value.get(key)
    return nested.get("enabled") if isinstance(nested, dict) else None


class GitHubClient:
    def __init__(self, token: str | None = None) -> None:
        self.token = token

    def _request(self, url: str, accept: str) -> str:
        headers = {
            "Accept": accept,
            "User-Agent": "tactevra-repository-health-audit",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=20) as response:
                return response.read().decode("utf-8")
        except HTTPError as exc:
            raise RuntimeError(f"GET {url} returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"GET {url} failed: {exc.reason}") from exc

    def json(self, path: str) -> object:
        return json.loads(self._request(f"https://api.github.com{path}", "application/vnd.github+json"))

    def text(self, url: str) -> str:
        return self._request(url, "text/html")


def write_summary(path: str | None, scope: str, rows: list[tuple[str, str]], errors: list[str]) -> None:
    if not path:
        return
    lines = ["## Tactevra repository health", "", f"Scope: `{scope}` (read-only)", "", "| Check | Result |", "| --- | --- |"]
    lines.extend(f"| {name} | {result} |" for name, result in rows)
    if errors:
        lines.extend(["", "### Drift", ""])
        lines.extend(f"- {error}" for error in errors)
    with Path(path).open("a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy-only", action="store_true")
    parser.add_argument("--scope", choices=("public", "owner"), default="public")
    parser.add_argument("--repository")
    parser.add_argument("--summary")
    args = parser.parse_args()
    policy, errors = load_policy()
    if errors or policy is None:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    if args.repository and args.repository != policy["repository"]:
        print(
            f"ERROR: repository mismatch: policy names {policy['repository']!r}, "
            f"runtime names {args.repository!r}"
        )
        return 1
    if args.policy_only:
        print("PASS: repository-health policy is valid strict JSON")
        return 0

    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    client = GitHubClient(token)
    try:
        live_errors, rows = evaluate_public(policy, client.json, client.text)
        if args.scope == "owner":
            owner_errors, owner_rows = evaluate_owner(policy, client.json)
            live_errors.extend(owner_errors)
            rows.extend(owner_rows)
    except (RuntimeError, json.JSONDecodeError) as exc:
        live_errors = [str(exc)]
        rows = [("GitHub API availability", "error")]
    write_summary(args.summary, args.scope, rows, live_errors)
    if live_errors:
        for error in live_errors:
            print(f"ERROR: {error}")
        return 1
    print(f"PASS: {args.scope} repository settings match the declared health policy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
