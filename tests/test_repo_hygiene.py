"""Repo-wide guards for the hard rules in CLAUDE.md.

These run on every pull request. They check what git tracks, so local
gitignored files (terraform.tfvars, .terraform/) never trip them.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

# Access key IDs: AKIA (long-term) / ASIA (temporary) + 16 upper-case alphanumerics.
AWS_ACCESS_KEY_ID = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
# A 40-character secret assigned to something that looks like a secret key name.
AWS_SECRET_ASSIGNMENT = re.compile(
    r"(?i)aws_?secret_?access_?key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}\b"
)
PRIVATE_KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")
# A 12-digit AWS account ID inside an ARN. The repo is public, so account IDs
# are passed at runtime (GitHub variables, -backend-config), not committed.
ACCOUNT_ID_IN_ARN = re.compile(r"arn:aws[a-z-]*:[a-z0-9-]*:[a-z0-9-]*:(\d{12}):")
PLACEHOLDER_ACCOUNT_IDS = {"123456789012", "000000000000", "111111111111"}

FORBIDDEN_NAMES = {".env"}
FORBIDDEN_SUFFIXES = (".tfstate", ".tfstate.backup", ".tfvars", ".pem", ".key")
BINARY_SUFFIXES = (".png", ".jpg", ".jpeg", ".gif", ".pdf", ".ico", ".zip", ".parquet")


def tracked_files() -> list[Path]:
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    ).stdout
    return [REPO_ROOT / p for p in out.decode().split("\0") if p]


def text_files() -> list[Path]:
    return [p for p in tracked_files() if p.is_file() and not p.name.lower().endswith(BINARY_SUFFIXES)]


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_git_lists_files():
    assert tracked_files(), "git ls-files returned nothing; run tests from inside the repo"


def test_no_secret_or_state_files_tracked():
    bad = [
        rel(p)
        for p in tracked_files()
        if p.name in FORBIDDEN_NAMES
        or p.name.startswith(".env.")
        or p.name.endswith(FORBIDDEN_SUFFIXES)
    ]
    assert not bad, f"Secret, state or tfvars files must not be committed: {bad}"


def test_no_aws_credentials_in_code():
    hits = []
    for p in text_files():
        text = read(p)
        for pattern in (AWS_ACCESS_KEY_ID, AWS_SECRET_ASSIGNMENT, PRIVATE_KEY):
            if pattern.search(text):
                hits.append(f"{rel(p)}: {pattern.pattern[:30]}...")
    assert not hits, f"Possible credentials committed: {hits}"


def test_no_real_account_ids_in_arns():
    hits = []
    for p in text_files():
        for match in ACCOUNT_ID_IN_ARN.finditer(read(p)):
            if match.group(1) not in PLACEHOLDER_ACCOUNT_IDS:
                hits.append(rel(p))
    assert not hits, f"Real AWS account IDs found in: {sorted(set(hits))}. Use variables instead."


def test_workflows_use_oidc_not_stored_keys():
    workflows = [p for p in text_files() if rel(p).startswith(".github/workflows/") and p.suffix in {".yml", ".yaml"}]
    for wf in workflows:
        text = read(wf)
        assert "aws-access-key-id" not in text, f"{rel(wf)} uses stored AWS keys; use role-to-assume (OIDC)"
        assert "AWS_SECRET_ACCESS_KEY" not in text, f"{rel(wf)} references AWS_SECRET_ACCESS_KEY"


@pytest.mark.parametrize("stack", ["infra/envs/dev", "infra/envs/prod", "infra/bootstrap"])
def test_stacks_use_locked_s3_backend(stack):
    backend = read(REPO_ROOT / stack / "backend.tf")
    active = "\n".join(line for line in backend.splitlines() if not line.lstrip().startswith("#"))
    assert 'backend "s3"' in active, f"{stack} must use the S3 backend"
    assert re.search(r"use_lockfile\s*=\s*true", active), f"{stack} must enable state locking"
    assert re.search(r"encrypt\s*=\s*true", active), f"{stack} must encrypt state"


def test_env_stacks_have_separate_state_keys():
    keys = {}
    for env in ("dev", "prod"):
        m = re.search(r'key\s*=\s*"([^"]+)"', read(REPO_ROOT / "infra/envs" / env / "backend.tf"))
        assert m, f"{env} backend has no key"
        keys[env] = m.group(1)
    assert keys["dev"].startswith("dev/") and keys["prod"].startswith("prod/"), keys
    assert keys["dev"] != keys["prod"]
