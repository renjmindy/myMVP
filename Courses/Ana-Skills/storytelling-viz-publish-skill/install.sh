#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_NAME="storytelling-viz-publish"
DEST="${HOME}/.claude/skills/${SKILL_NAME}"

mkdir -p "${DEST}"
cp "${SCRIPT_DIR}/SKILL.md" "${DEST}/SKILL.md"

printf 'Installed to %s\n' "${DEST}"
