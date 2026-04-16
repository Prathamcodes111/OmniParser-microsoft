#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT_DIR"

WEIGHTS_DIR="${OMNIPARSER_WEIGHTS_DIR:-$ROOT_DIR/weights}"
mkdir -p "$WEIGHTS_DIR"

if [[ ! -f "$WEIGHTS_DIR/icon_detect/model.pt" || ! -f "$WEIGHTS_DIR/icon_caption_florence/model.safetensors" ]]; then
  echo "[OmniParser] weights missing - downloading microsoft/OmniParser-v2.0..."
  for f in \
    icon_detect/train_args.yaml \
    icon_detect/model.pt \
    icon_detect/model.yaml \
    icon_caption/config.json \
    icon_caption/generation_config.json \
    icon_caption/model.safetensors
  do
    huggingface-cli download microsoft/OmniParser-v2.0 "$f" --local-dir "$WEIGHTS_DIR"
  done
  if [[ -d "$WEIGHTS_DIR/icon_caption" && ! -d "$WEIGHTS_DIR/icon_caption_florence" ]]; then
    mv "$WEIGHTS_DIR/icon_caption" "$WEIGHTS_DIR/icon_caption_florence"
  fi
fi

# Paddle 3 PIR inference can SIGSEGV in Docker/ARM; default to legacy path before any imports.
export FLAGS_enable_pir_api="${FLAGS_enable_pir_api:-0}"
# Optional: skip PaddleX remote model host checks on startup.
export PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK="${PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK:-True}"

exec python -m uvicorn fastapi_service:app --host 0.0.0.0 --port "${PORT:-7860}"
