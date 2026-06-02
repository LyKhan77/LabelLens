#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${PORT:-3131}"
FRONTEND_PORT="${FRONTEND_PORT:-8282}"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/env/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python tidak ditemukan. Set PYTHON_BIN atau install python3."
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "npm tidak ditemukan. Install Node.js + npm dulu."
  exit 1
fi

cleanup() {
  trap - EXIT INT TERM
  echo ""
  echo "Stopping frontend + backend..."
  [[ -n "${BACKEND_PID:-}" ]] && kill "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && kill "$FRONTEND_PID" 2>/dev/null || true
  [[ -n "${BACKEND_PID:-}" ]] && wait "$BACKEND_PID" 2>/dev/null || true
  [[ -n "${FRONTEND_PID:-}" ]] && wait "$FRONTEND_PID" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

echo "Starting backend on :$BACKEND_PORT ..."
(
  cd "$ROOT_DIR"
  CUDA_DEVICE_ORDER="${CUDA_DEVICE_ORDER:-PCI_BUS_ID}" \
  "$PYTHON_BIN" -m uvicorn backend.main:app \
    --host "${HOST:-0.0.0.0}" \
    --port "$BACKEND_PORT" \
    --reload
) &
BACKEND_PID=$!

echo "Starting frontend on :$FRONTEND_PORT ..."
(
  cd "$ROOT_DIR/frontend"
  npm run dev -- --host 0.0.0.0 --port "$FRONTEND_PORT"
) &
FRONTEND_PID=$!

echo "Frontend: http://localhost:$FRONTEND_PORT"
echo "Backend : http://localhost:$BACKEND_PORT"
echo "Press Ctrl+C untuk stop semua service."

wait -n "$BACKEND_PID" "$FRONTEND_PID"
EXIT_CODE=$?
echo "Salah satu service berhenti (exit code: $EXIT_CODE)."
exit "$EXIT_CODE"
