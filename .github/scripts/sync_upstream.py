"""Fast-forward the official mirror and open an internal integration PR."""

import os
from pathlib import Path
import subprocess
import tempfile


def run(*args):
    return subprocess.check_output(args, text=True).strip()


def is_ancestor(older, newer):
    result = subprocess.run(["git", "merge-base", "--is-ancestor", older, newer],
                            check=False)
    if result.returncode != 1:
        result.check_returncode()
    return result.returncode == 0


def sync_main(source):
    run("git", "fetch", "--no-tags", "origin",
        "+refs/heads/main:refs/remotes/origin/main",
        "+refs/heads/internal/main:refs/remotes/origin/internal/main")
    run("git", "fetch", "--no-tags", source,
        "+refs/heads/main:refs/remotes/official/main")
    mirror = run("git", "rev-parse", "refs/remotes/origin/main")
    internal = run("git", "rev-parse", "refs/remotes/origin/internal/main")
    upstream = run("git", "rev-parse", "refs/remotes/official/main")
    if not is_ancestor(mirror, upstream):
        raise SystemExit(f"Refusing non-fast-forward update of main: {mirror} -> {upstream}")
    if mirror != upstream:
        run("git", "push", "--no-follow-tags", "origin", f"{upstream}:refs/heads/main")
    return upstream, internal, not is_ancestor(upstream, internal)


def main():
    repository = os.environ["GITHUB_REPOSITORY"]
    if repository != "profiling/git-cache-proxy":
        raise SystemExit("This workflow only maintains profiling/git-cache-proxy")
    official_sha, internal_sha, pending = sync_main(
        "https://github.com/rolandjitsu/git-cache-proxy.git")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="ascii") as output:
        output.write(f"pending={str(pending).lower()}\n")
        output.write(f"official_sha={official_sha}\n")
        output.write(f"internal_sha={internal_sha}\n")
    if not pending:
        return
    # A contributor's fork can also have a branch named main.
    existing = run("gh", "pr", "list", "--repo", repository, "--state", "open",
                   "--base", "internal/main", "--head", "main",
                   "--json", "url,isCrossRepository", "--jq",
                   "map(select(.isCrossRepository == false)) | .[0].url // empty")
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
