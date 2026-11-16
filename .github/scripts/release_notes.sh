#!/usr/bin/env bash
# Write the internal release notes to stdout.
# Env: TAG COMMIT IMAGE DIGEST RUN_URL, plus OLD_HELP/NEW_HELP when a previous tag
# exists. Run from the repo root after the image is pushed.
set -euo pipefail

ref=$IMAGE@$DIGEST
build_base=$(awk '/^FROM .* AS build/ {print $2}' Dockerfile)
run_base=$(awk '/^FROM / && !/AS build/ {print $2}' Dockerfile)
rustc_version=$(docker run --rm --entrypoint rustc "$build_base" --version)
git_version=$(docker run --rm --entrypoint git "$ref" --version)
lock_sha=$(sha256sum Cargo.lock | cut -d' ' -f1)
official_base=$(git merge-base origin/main "$COMMIT" 2>/dev/null || echo unknown)
prev=$(git tag --list 'internal-v*' --sort=-v:refname | grep -vx "$TAG" | head -1 || true)

cat <<NOTES
## Image

- Image: \`$IMAGE\`
- Manifest digest: \`$DIGEST\`
- Pull: \`docker pull $ref\`
- Tags: \`$TAG\`, \`$COMMIT\`
- Platform: linux/amd64

## Build

- Commit: \`$COMMIT\`
- Official main base: \`$official_base\`
- Run: $RUN_URL
- Compiler: \`$rustc_version\` (\`cargo build --release --locked\`)
- Cargo.lock SHA256: \`$lock_sha\`
- Git in image: \`$git_version\`
- Base images (floating tags, as pulled by this build): \`$build_base\`, \`$run_base\`

## CLI changes since ${prev:-"(no previous internal tag)"}

NOTES
if [ -n "$prev" ]; then
  python3 -I .github/scripts/cli_diff.py "$OLD_HELP" "$NEW_HELP"
fi
