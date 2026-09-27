import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import check_repository_health as health


def policy() -> dict[str, object]:
    return {
        "schema": health.SCHEMA,
        "repository": "j-webtek/tactevra",
        "public": {
            "repository_fields": {"visibility": "public", "default_branch": "main"},
            "default_branch_protected": True,
            "minimum_community_health_percentage": 100,
            "required_workflows": {".github/workflows/offline-checks.yml": "active"},
            "pages": {"url": "https://example.test/", "title_contains": "Tactevra"},
        },
        "owner": {
            "repository_fields": {
                "allow_squash_merge": True,
                "allow_merge_commit": False,
                "allow_rebase_merge": False,
                "delete_branch_on_merge": True,
            },
            "security_and_analysis": {"secret_scanning": "enabled"},
            "branch_protection": {
                "strict_status_checks": True,
                "required_status_contexts": ["CodeQL"],
                "enforce_admins": True,
                "dismiss_stale_reviews": True,
                "required_approving_review_count": 0,
                "required_linear_history": True,
                "required_conversation_resolution": True,
                "allow_force_pushes": False,
                "allow_deletions": False,
            },
            "actions": {
                "enabled": True,
                "allowed_actions": "selected",
                "sha_pinning_required": True,
                "github_owned_allowed": False,
                "verified_allowed": False,
                "patterns_allowed": ["actions/checkout@*"],
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": False,
            },
            "pages": {
                "html_url": "https://example.test/",
                "build_type": "workflow",
                "public": True,
                "https_enforced": True,
                "source_branch": "main",
                "source_path": "/",
            },
        },
    }


class RepositoryHealthTests(unittest.TestCase):
    def test_valid_policy(self):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "policy.json"
            path.write_text(json.dumps(policy()), encoding="utf-8")
            loaded, errors = health.load_policy(path)
            self.assertEqual([], errors)
            self.assertEqual("j-webtek/tactevra", loaded["repository"])

    def test_invalid_policy_schema(self):
        with TemporaryDirectory() as folder:
            value = policy()
            value["schema"] = "wrong"
            path = Path(folder) / "policy.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            _, errors = health.load_policy(path)
            self.assertTrue(any("schema" in error for error in errors))

    def public_fetch(self, drift: bool = False):
        responses = {
            "/repos/j-webtek/tactevra": {
                "visibility": "private" if drift else "public", "default_branch": "main"
            },
            "/repos/j-webtek/tactevra/branches/main": {"protected": True},
            "/repos/j-webtek/tactevra/community/profile": {"health_percentage": 100},
            "/repos/j-webtek/tactevra/actions/workflows": {
                "workflows": [{"path": ".github/workflows/offline-checks.yml", "state": "active"}]
            },
        }
        return lambda path: responses[path]

    def test_public_health_passes(self):
        errors, rows = health.evaluate_public(
            policy(), self.public_fetch(), lambda _: "<title>Tactevra</title>"
        )
        self.assertEqual([], errors)
        self.assertTrue(all(result == "pass" for _, result in rows))

    def test_public_metadata_drift_fails(self):
        errors, _ = health.evaluate_public(
            policy(), self.public_fetch(drift=True), lambda _: "<title>Tactevra</title>"
        )
        self.assertTrue(any("visibility" in error for error in errors))

    def test_public_page_drift_fails(self):
        errors, _ = health.evaluate_public(
            policy(), self.public_fetch(), lambda _: "<title>Wrong</title>"
        )
        self.assertTrue(any("Pages title" in error for error in errors))

    def test_owner_health_passes(self):
        responses = {
            "/repos/j-webtek/tactevra": {
                "allow_squash_merge": True,
                "allow_merge_commit": False,
                "allow_rebase_merge": False,
                "delete_branch_on_merge": True,
                "security_and_analysis": {"secret_scanning": {"status": "enabled"}}
            },
            "/repos/j-webtek/tactevra/branches/main/protection": {
                "required_status_checks": {"strict": True, "contexts": ["CodeQL"]},
                "enforce_admins": {"enabled": True},
                "required_pull_request_reviews": {
                    "dismiss_stale_reviews": True, "required_approving_review_count": 0
                },
                "required_linear_history": {"enabled": True},
                "required_conversation_resolution": {"enabled": True},
                "allow_force_pushes": {"enabled": False},
                "allow_deletions": {"enabled": False},
            },
            "/repos/j-webtek/tactevra/actions/permissions": {
                "enabled": True, "allowed_actions": "selected", "sha_pinning_required": True
            },
            "/repos/j-webtek/tactevra/actions/permissions/selected-actions": {
                "github_owned_allowed": False,
                "verified_allowed": False,
                "patterns_allowed": ["actions/checkout@*"],
            },
            "/repos/j-webtek/tactevra/actions/permissions/workflow": {
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": False,
            },
            "/repos/j-webtek/tactevra/pages": {
                "html_url": "https://example.test/",
                "build_type": "workflow",
                "public": True,
                "https_enforced": True,
                "source": {"branch": "main", "path": "/"},
            },
        }
        errors, rows = health.evaluate_owner(policy(), lambda path: responses[path])
        self.assertEqual([], errors)
        self.assertTrue(all(result == "pass" for _, result in rows))

    def test_owner_protection_drift_fails(self):
        value = policy()
        value["owner"]["branch_protection"]["enforce_admins"] = False
        responses = {
            "/repos/j-webtek/tactevra": {
                "allow_squash_merge": True,
                "allow_merge_commit": False,
                "allow_rebase_merge": False,
                "delete_branch_on_merge": True,
                "security_and_analysis": {"secret_scanning": {"status": "enabled"}}
            },
            "/repos/j-webtek/tactevra/branches/main/protection": {
                "required_status_checks": {"strict": True, "contexts": ["CodeQL"]},
                "enforce_admins": {"enabled": True},
                "required_pull_request_reviews": {
                    "dismiss_stale_reviews": True, "required_approving_review_count": 0
                },
                "required_linear_history": {"enabled": True},
                "required_conversation_resolution": {"enabled": True},
                "allow_force_pushes": {"enabled": False},
                "allow_deletions": {"enabled": False},
            },
            "/repos/j-webtek/tactevra/actions/permissions": {
                "enabled": True, "allowed_actions": "selected", "sha_pinning_required": True
            },
            "/repos/j-webtek/tactevra/actions/permissions/selected-actions": {
                "github_owned_allowed": False,
                "verified_allowed": False,
                "patterns_allowed": ["actions/checkout@*"],
            },
            "/repos/j-webtek/tactevra/actions/permissions/workflow": {
                "default_workflow_permissions": "read",
                "can_approve_pull_request_reviews": False,
            },
            "/repos/j-webtek/tactevra/pages": {
                "html_url": "https://example.test/",
                "build_type": "workflow",
                "public": True,
                "https_enforced": True,
                "source": {"branch": "main", "path": "/"},
            },
        }
        errors, _ = health.evaluate_owner(value, lambda path: responses[path])
        self.assertTrue(any("enforce_admins" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
