#!/bin/bash
# Optional: installs the visual-only Codex pet, separate from offline assistant.
set -e
cd "$(dirname "$0")" || exit 1
mkdir -p "${CODEX_HOME:-$HOME/.codex}/pets"
cp -R einstein-chibi "${CODEX_HOME:-$HOME/.codex}/pets/"
echo "Einstein Codex visual pet installed. Restart Codex and select it under Pets."
