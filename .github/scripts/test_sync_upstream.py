"""Exercise mirror updates against local Git repositories."""

import os
import re
from types import SimpleNamespace
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sync_upstream

from sync_upstream import run, sync_main


class SyncTests(unittest.TestCase):
    def test_new_official_commit_opens_integration_candidate(self):
        self.commit(self.official, "official", "new")
        self.assertTrue(sync_main(str(self.official)))
        self.assertEqual(run("git", "rev-parse", "official/main"),
                         run("git", "--git-dir", str(self.remote), "rev-parse", "main"))
        self.assertEqual(self.internal_sha,
                         run("git", "--git-dir", str(self.remote), "rev-parse", "internal/main"))
        self.assertTrue(sync_main(str(self.official)))

    def test_already_integrated_official_commit_needs_no_pr(self):
        self.assertFalse(sync_main(str(self.official)))

    def test_diverged_mirror_is_preserved(self):
        self.commit(self.checkout, "private", "keep")
        run("git", "push", "origin", "HEAD:main")
        old = run("git", "--git-dir", str(self.remote), "rev-parse", "main")
        self.commit(self.official, "official", "new")
        with self.assertRaises(subprocess.CalledProcessError):
            sync_main(str(self.official))
        self.assertEqual(old, run("git", "--git-dir", str(self.remote), "rev-parse", "main"))

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.previous = Path.cwd()
        self.addCleanup(os.chdir, self.previous)
        root = Path(self.directory.name)
        self.official = root / "official"
        self.remote = root / "fork.git"
        self.checkout = root / "checkout"
        run("git", "init", str(self.official))
        run("git", "-C", str(self.official), "symbolic-ref", "HEAD", "refs/heads/main")
        self.commit(self.official, "base", "base")
        run("git", "clone", "--bare", str(self.official), str(self.remote))
        run("git", "clone", str(self.remote), str(self.checkout))
        os.chdir(self.checkout)
        run("git", "checkout", "-b", "internal/main")
        self.commit(self.checkout, "internal", "internal")
        self.internal_sha = run("git", "rev-parse", "HEAD")
        run("git", "push", "origin", "internal/main")

    def commit(self, directory, name, contents):
        (directory / name).write_text(contents, encoding="ascii")
        run("git", "-C", str(directory), "add", name)
        run("git", "-C", str(directory), "-c", "user.name=Test",
            "-c", "user.email=test@example.invalid", "-c", "commit.gpgsign=false",
            "commit", "-m", "test: add fixture")


class PullRequestTests(unittest.TestCase):
    def test_create_pr_when_updates_are_pending(self):
        commands, outputs = self.invoke(True, "")
        self.assertTrue(any(command[:3] == ("gh", "pr", "create") for command in commands))
        self.assertIn("pending=true", outputs)
        self.assertIn("official_sha=official-sha", outputs)
        self.assertIn("internal_sha=internal-sha", outputs)

    def test_reuse_existing_pr(self):
        commands, _ = self.invoke(True, "https://github.com/profiling/git-cache-proxy/pull/1")
        self.assertTrue(any(command[:3] == ("gh", "pr", "edit") for command in commands))
        self.assertFalse(any(command[:3] == ("gh", "pr", "create") for command in commands))

    def test_no_pr_when_official_is_integrated(self):
        commands, outputs = self.invoke(False, "")
        self.assertFalse(any(command[0] == "gh" for command in commands))
        self.assertIn("pending=false", outputs)

    def invoke(self, pending, existing):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "outputs"
            environment = {
                "GITHUB_REPOSITORY": "profiling/git-cache-proxy",
                "GITHUB_OUTPUT": str(output),
                "GITHUB_SERVER_URL": "https://github.com",
                "GITHUB_RUN_ID": "123",
            }
            commands = []

            def fake_run(*args):
                commands.append(args)
                if args[:3] == ("git", "rev-parse", "official/main"):
                    return "official-sha"
                if args[:3] == ("git", "rev-parse", "origin/internal/main"):
                    return "internal-sha"
                if args[:3] == ("gh", "pr", "list"):
                    return existing
                if "--body-file" in args:
                    body = Path(args[args.index("--body-file") + 1]).read_text()
                    self.assertIn("official-sha", body)
                    self.assertIn("internal-sha", body)
                    self.assertIn("actions/runs/123", body)
                return "https://github.com/profiling/git-cache-proxy/pull/1"

            with patch.dict(os.environ, environment), patch.object(
                sync_upstream, "sync_main", return_value=pending
            ), patch.object(sync_upstream, "run", side_effect=fake_run):
                sync_upstream.main()
            return commands, output.read_text()


class CommitPolicyTests(unittest.TestCase):
    def test_only_same_fork_official_syncs_are_exempt(self):
        workflow = (Path(__file__).resolve().parents[1] / "workflows" / "ci.yml").read_text()
        expression = re.search(
            r"      - if: >-\n(.*?)        uses: crate-ci/committed", workflow, re.S
        ).group(1)
        expression = " ".join(expression.split()).replace("&&", " and ")
        expression = re.sub(r"!(?!=)", "not ", expression)
        repository = "profiling/git-cache-proxy"
        cases = [
            (repository, repository, "main", "internal/main", "github-actions[bot]", False),
            (repository, repository, "fix/example", "internal/main", "profiling", True),
            (repository, "other/git-cache-proxy", "main", "internal/main", "other", True),
            (repository, repository, "main", "main", "profiling", True),
            ("other/repo", "other/repo", "main", "internal/main", "other", True),
            (repository, repository, "fix/example", "internal/main", "dependabot[bot]", False),
        ]
        for repo, head_repo, head, base, author, expected in cases:
            with self.subTest(repo=repo, head_repo=head_repo, head=head, base=base, author=author):
                github = SimpleNamespace(
                    repository=repo,
                    event=SimpleNamespace(pull_request=SimpleNamespace(
                        user=SimpleNamespace(login=author),
                        head=SimpleNamespace(repo=SimpleNamespace(full_name=head_repo), ref=head),
                        base=SimpleNamespace(ref=base),
                    )),
                )
                self.assertEqual(
                    eval(expression, {"__builtins__": {}}, {"github": github}), expected
                )


if __name__ == "__main__":
    unittest.main()
