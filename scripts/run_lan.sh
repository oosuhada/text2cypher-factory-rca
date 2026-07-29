#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

API_PID=""
WEB_PID=""
STREAMLIT_PID=""

cleanup() {
  [[ -z "$WEB_PID" ]] || kill "$WEB_PID" 2>/dev/null || true
  [[ -z "$STREAMLIT_PID" ]] || kill "$STREAMLIT_PID" 2>/dev/null || true
  [[ -z "$API_PID" ]] || kill "$API_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

detect_lan_ip() {
  if [[ -n "${P3_LAN_IP:-}" ]]; then
    printf '%s\n' "$P3_LAN_IP"
    return
  fi

  if command -v ipconfig >/dev/null 2>&1; then
    local candidate
    for interface in en0 en1; do
      candidate="$(ipconfig getifaddr "$interface" 2>/dev/null || true)"
      if [[ -n "$candidate" ]]; then
        printf '%s\n' "$candidate"
        return
      fi
    done
  fi

  if command -v hostname >/dev/null 2>&1; then
    local candidate
    candidate="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
    if [[ -n "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  fi

  if command -v ip >/dev/null 2>&1; then
    local candidate
    candidate="$(ip route get 1.1.1.1 2>/dev/null | awk '{for (i=1; i<=NF; i++) if ($i == "src") {print $(i+1); exit}}' || true)"
    if [[ -n "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return
    fi
  fi

  return 1
}

LAN_IP="$(detect_lan_ip || true)"
if [[ -z "$LAN_IP" ]]; then
  echo "LAN IP를 자동 감지하지 못했습니다. P3_LAN_IP=192.168.x.x 형태로 지정하세요." >&2
  exit 1
fi

API_PORT="${P3_API_PORT:-8000}"
WEB_PORT="${P3_WEB_PORT:-3000}"
STREAMLIT_PORT="${P3_STREAMLIT_PORT:-8501}"

export P3_API_HOST="0.0.0.0"
export P3_WEB_HOST="0.0.0.0"
export P3_API_PROVIDER="${P3_API_PROVIDER:-gold}"
export P3_LANGGRAPH_CHECKPOINT_BACKEND="${P3_LANGGRAPH_CHECKPOINT_BACKEND:-sqlite}"
export P3_RAG_BOOTSTRAP_FIXTURES="${P3_RAG_BOOTSTRAP_FIXTURES:-1}"
export P3_RAG_SIMILARITY_CUTOFF="${P3_RAG_SIMILARITY_CUTOFF:-0.04}"
export LANGGRAPH_STRICT_MSGPACK="${LANGGRAPH_STRICT_MSGPACK:-true}"
export P3_API_PORT="$API_PORT"
export P3_WEB_PORT="$WEB_PORT"
export P3_CORS_ORIGINS="${P3_CORS_ORIGINS:-http://localhost:${WEB_PORT},http://127.0.0.1:${WEB_PORT},http://${LAN_IP}:${WEB_PORT}}"
export NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://${LAN_IP}:${API_PORT}}"
export NEXT_PUBLIC_INTERNAL_CONSOLE_URL="${NEXT_PUBLIC_INTERNAL_CONSOLE_URL:-http://${LAN_IP}:${STREAMLIT_PORT}}"
export LAN_SHARE=1

./scripts/run_api.sh &
API_PID=$!

for _ in {1..40}; do
  if curl --silent --fail "http://127.0.0.1:${API_PORT}/api/v1/health/live" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
if ! curl --silent --fail "http://127.0.0.1:${API_PORT}/api/v1/health/live" >/dev/null 2>&1; then
  echo "FastAPI가 제한 시간 안에 시작되지 않았습니다." >&2
  exit 1
fi

./scripts/run_streamlit.sh \
  --server.address 0.0.0.0 \
  --server.port "$STREAMLIT_PORT" \
  --server.headless true &
STREAMLIT_PID=$!

./scripts/run_web.sh &
WEB_PID=$!

echo "FactoryGraph RCA LAN 공유 서버"
echo "- Product UI:      http://${LAN_IP}:${WEB_PORT}"
echo "- Internal Console: http://${LAN_IP}:${STREAMLIT_PORT}"
echo "- API docs:        http://${LAN_IP}:${API_PORT}/docs"
echo "- Local Product UI: http://127.0.0.1:${WEB_PORT}"
echo "같은 Wi-Fi/LAN의 팀원은 위 LAN 주소를 사용하세요. macOS 방화벽에서 Python, Node.js, Streamlit의 수신 연결을 허용해야 할 수 있습니다."

wait "$WEB_PID"
