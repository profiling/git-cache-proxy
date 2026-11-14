"""Fast-forward the official mirror and open an internal integration PR."""

import os
from pathlib import Path
import subprocess
import tempfile


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def sync_main(source, remote="origin"):
    run("git", "fetch", "--no-tags", remote,
        "+refs/heads/main:refs/remotes/origin/main",
        "+refs/heads/internal/main:refs/remotes/origin/internal/main")
    run("git", "fetch", "--no-tags", source,
        "+refs/heads/main:refs/remotes/official/main")
    # Never overwrite internal work accidentally added to the mirror.
    run("git", "merge-base", "--is-ancestor", "origin/main", "official/main")
    run("git", "push", remote, "refs/remotes/official/main:refs/heads/main")
    result = subprocess.run([
        "git", "merge-base", "--is-ancestor", "official/main", "origin/internal/main"
    ], check=False)
    if result.returncode not in (0, 1):
        result.check_returncode()
    return result.returncode == 1


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    if repository != "profiling/git-cache-proxy":
        raise SystemExit("This workflow only maintains profiling/git-cache-proxy")
    pending = sync_main("https://github.com/rolandjitsu/git-cache-proxy.git")
    official_sha = run("git", "rev-parse", "official/main")
    internal_sha = run("git", "rev-parse", "origin/internal/main")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="ascii") as output:
        output.write(f"pending={str(pending).lower()}\n")
        output.write(f"official_sha={official_sha}\n")
        output.write(f"internal_sha={internal_sha}\n")
    if not pending:
        return
    existing = run("gh", "pr", "list", "--repo", repository, "--state", "open",
                   "--base", "internal/main", "--head", "main", "--json", "url",
                   "--jq", ".[0].url // empty")
    with tempfile.TemporaryDirectory() as directory:
        body = Path(directory) / "body.md"
        body.write_text(
            "Merge the official main into the internal integration branch.\n\n"
            "Review conflicts and the Internal maintenance workflow before merging.\n"
            "The workflow validates the merged tree without deploying it.\n\n"
            f"Official head: `{official_sha}`\n\nInternal base: `{internal_sha}`\n\n"
            f"Validation: {os.environ['GITHUB_SERVER_URL']}/{repository}/actions/runs/"
            f"{os.environ['GITHUB_RUN_ID']}\n", encoding="ascii")
        if existing:
            run("gh", "pr", "edit", existing, "--repo", repository, "--body-file", str(body))
            print(existing)
            return
        print(run("gh", "pr", "create", "--repo", repository, "--base", "internal/main",
                  "--head", "main", "--title", "chore: integrate official main",
                  "--body-file", str(body)))


if __name__ == "__main__":
    main()
