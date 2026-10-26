#!/usr/bin/env bash
set -euo pipefail
: "${SYNC_TARGET:?Set SYNC_TARGET to user@host:/path/ before syncing}"
rsync -e ssh -av --progress --exclude-from=.syncignore ./ "${SYNC_TARGET}"
