#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "❌ ENV file not found: $ENV_FILE" >&2
  exit 1
fi

# 讀取指定 key 的值（不執行檔案內容）
# - 忽略空行與註解
# - 允許 key 前後有空白
# - 允許 value 用單/雙引號包起來
get_env() {
  local key="$1"
  local line value

  # 取最後一次出現的 key（後面的覆蓋前面）
  line="$(
    grep -E "^[[:space:]]*${key}[[:space:]]*=" "$ENV_FILE" | tail -n 1 || true
  )"

  if [[ -z "$line" ]]; then
    echo ""
    return 0
  fi

  value="${line#*=}"                       # 去掉 key=
  value="$(echo "$value" | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"  # trim

  # 去掉包住整個 value 的單/雙引號（可選）
  if [[ "$value" =~ ^\".*\"$ ]]; then
    value="${value:1:${#value}-2}"
  elif [[ "$value" =~ ^\'.*\'$ ]]; then
    value="${value:1:${#value}-2}"
  fi

  echo "$value"
}

require_env() {
  local key="$1"
  local val
  val="$(get_env "$key")"
  if [[ -z "$val" ]]; then
    echo "❌ Missing required env key in $ENV_FILE: $key" >&2
    exit 1
  fi
  printf '%s' "$val"
}

export CLICKHOUSE_URL="$(require_env CLICKHOUSE_URL)"
export CLICKHOUSE_USER="$(require_env CLICKHOUSE_USER)"
export CLICKHOUSE_PASSWORD="$(require_env CLICKHOUSE_PASSWORD)"

# 可選：你也可以在這裡 export 更多 key（例如 DB 名稱）
export CLICKHOUSE_DB="$(get_env CLICKHOUSE_DB || true)"
export CLICKHOUSE_DB="${CLICKHOUSE_DB:-analytics}"