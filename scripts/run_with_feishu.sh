#!/usr/bin/env bash
# Run crawler and push CSV(s) to Feishu.
#
# 1) Copy feishu.env.example -> feishu.env and fill in credentials, OR export the three vars in your shell.
# 2) chmod +x scripts/run_with_feishu.sh
# 3) ./scripts/run_with_feishu.sh
#
# Optional: CONFIG=config.yaml ./scripts/run_with_feishu.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ENV_FILE="${FEISHU_ENV_FILE:-$ROOT/feishu.env}"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
fi

: "${FEISHU_APP_ID:?missing FEISHU_APP_ID (export it or create feishu.env from feishu.env.example)}"
: "${FEISHU_APP_SECRET:?missing FEISHU_APP_SECRET}"
: "${FEISHU_CHAT_ID:?missing FEISHU_CHAT_ID}"

CONFIG="${CONFIG:-config.yaml}"

if [[ -x "/opt/anaconda3/envs/future/bin/python" ]]; then
  PYTHON="${PYTHON:-/opt/anaconda3/envs/future/bin/python}"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="${PYTHON:-$ROOT/.venv/bin/python}"
else
  PYTHON="${PYTHON:-python3}"
fi

if [[ "${VERBOSE:-0}" == "1" ]]; then
  exec "$PYTHON" -m futures_crawler.cli run \
    --config "$CONFIG" \
    --feishu-app-id "$FEISHU_APP_ID" \
    --feishu-app-secret "$FEISHU_APP_SECRET" \
    --feishu-chat-id "$FEISHU_CHAT_ID" \
    --verbose
else
  exec "$PYTHON" -m futures_crawler.cli run \
    --config "$CONFIG" \
    --feishu-app-id "$FEISHU_APP_ID" \
    --feishu-app-secret "$FEISHU_APP_SECRET" \
    --feishu-chat-id "$FEISHU_CHAT_ID"
fi
