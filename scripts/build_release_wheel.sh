#!/usr/bin/env bash
# Bake the dashboard SPA and build a version-aligned raft wheel for GitHub Releases.
#
# Usage: scripts/build_release_wheel.sh <tag> [out-dir]
#   tag      Release tag (vX.Y.Z); wheel version is the tag without a leading v
#   out-dir  Directory for the .whl (default: dist/)
#
# Requires: Node/npm (src/spa), uv. Fails if the wheel lacks packaged SPA assets.
set -euo pipefail

TAG="${1:?usage: build_release_wheel.sh <vX.Y.Z> [out-dir]}"
OUT_DIR="${2:-dist}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="${TAG#v}"

if [[ ! "${VERSION}" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  echo "build_release_wheel.sh: expected tag vX.Y.Z, got ${TAG}" >&2
  exit 1
fi

cd "${ROOT}"

python3 - "${VERSION}" <<'PY'
import pathlib
import sys

version = sys.argv[1]
path = pathlib.Path("pyproject.toml")
lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
out = []
replaced = False
for line in lines:
    if line.startswith("version = ") and not replaced:
        out.append(f'version = "{version}"\n')
        replaced = True
    else:
        out.append(line)
if not replaced:
    raise SystemExit("pyproject.toml: missing version = line")
path.write_text("".join(out), encoding="utf-8")
print(f"pyproject version → {version}")
PY

echo "Baking SPA…"
(
  cd src/spa
  npm ci
  npm run build
)
test -f src/raft/core/platform/share/serve/spa/index.html
test -d src/raft/core/platform/share/serve/spa/assets

mkdir -p "${OUT_DIR}"
rm -f "${OUT_DIR}"/raft-"${VERSION}"-*.whl
echo "Building wheel…"
uv build --wheel --out-dir "${OUT_DIR}"

WHEEL="$(ls -1 "${OUT_DIR}"/raft-"${VERSION}"-*.whl | head -1)"
[[ -n "${WHEEL}" && -f "${WHEEL}" ]] || {
  echo "build_release_wheel.sh: no wheel for version ${VERSION} in ${OUT_DIR}" >&2
  exit 1
}

python3 - "${WHEEL}" <<'PY'
import sys
import zipfile

wheel = sys.argv[1]
needles = (
    "raft/core/platform/share/serve/spa/index.html",
    "raft/core/platform/share/compose.yaml",
)
with zipfile.ZipFile(wheel) as zf:
    names = set(zf.namelist())
missing = [n for n in needles if n not in names]
if missing:
    raise SystemExit(
        "wheel missing packaged assets:\n  " + "\n  ".join(missing)
    )
assets = [n for n in names if "/share/serve/spa/assets/" in n]
if not assets:
    raise SystemExit("wheel missing SPA hashed assets under share/serve/spa/assets/")
print(f"OK wheel {wheel} ({len(assets)} spa asset files)")
PY

printf 'wheel=%s\n' "${WHEEL}"
