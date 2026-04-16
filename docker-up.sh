#!/usr/bin/env bash
# One-shot: build image, run API on :7860, poll / until ready or timeout.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

IMAGE="${OMNIPARSER_IMAGE:-omniparser-v2-api:latest}"
NAME="${OMNIPARSER_CONTAINER:-omniparser-v2}"
PORT="${PORT:-7860}"

echo "==> [1/4] docker build -f Dockerfile.api -t ${IMAGE} ."
docker build -f Dockerfile.api -t "${IMAGE}" .

echo "==> [2/4] remove old container if any"
docker rm -f "${NAME}" 2>/dev/null || true

echo "==> [3/4] docker run -d -p ${PORT}:${PORT} --name ${NAME} ${IMAGE}"
docker run -d --rm -p "${PORT}:${PORT}" --name "${NAME}" "${IMAGE}"

echo "==> [4/4] wait for http://127.0.0.1:${PORT}/ (first boot may download weights; up to ~8 min)"
ok=0
for i in $(seq 1 32); do
  out="$(curl -sS --connect-timeout 3 "http://127.0.0.1:${PORT}/" 2>/dev/null || true)"
  if [[ -n "${out}" ]]; then
    echo "--- try ${i} ---"
    echo "${out}"
    if echo "${out}" | grep -q '"ready":true'; then
      ok=1
      break
    fi
  fi
  sleep 15
done

if [[ "${ok}" -eq 1 ]]; then
  echo ""
  echo "==> READY. Taskmaxer: TASKMAXER_OMNIPARSER_URL=http://127.0.0.1:${PORT}"
  exit 0
fi

echo ""
echo "==> Not ready in time. Last health + logs tail:"
curl -sS "http://127.0.0.1:${PORT}/" 2>/dev/null || echo "(no HTTP response)"
echo ""
docker logs "${NAME}" 2>&1 | tail -80
exit 1
