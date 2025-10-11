#!/usr/bin/env bash
set -euo pipefail

# Usage: scripts/run_taxonomy_staging.sh [-c config] [-e env_file]
# Defaults: config.staging.yaml, .env.staging (if present)

CONFIG_PATH="config.staging.yaml"
ENV_FILE=".env.staging"

while getopts "c:e:" opt; do
  case ${opt} in
    c)
      CONFIG_PATH="${OPTARG}"
      ;;
    e)
      ENV_FILE="${OPTARG}"
      ;;
    *)
      echo "Usage: $0 [-c config] [-e env_file]" >&2
      exit 1
      ;;
  esac
done

if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^#' "${ENV_FILE}" | xargs)
fi

STAMP=$(date -u +"%Y%m%dT%H%M%SZ")
BASE_DIR="artifacts/staging/${STAMP}"
LOG_DIR="${BASE_DIR}/logs"
OUTPUT_DIR="${BASE_DIR}/outputs"
TELEMETRY_DIR="${BASE_DIR}/telemetry"

mkdir -p "${LOG_DIR}" "${OUTPUT_DIR}" "${TELEMETRY_DIR}"

run_cmd() {
  local label=$1
  shift
  echo "[${STAMP}] Running ${label}..."
  "$@" | tee "${LOG_DIR}/${label}.log"
}

PYTHON=${PYTHON:-".venv/bin/python"}

run_cmd monitor "${PYTHON}" main.py monitor --config "${CONFIG_PATH}" --no-individual-issues --dry-run --verbose
run_cmd assign "${PYTHON}" main.py assign-workflows --config "${CONFIG_PATH}" --limit 15 --dry-run --verbose
run_cmd process "${PYTHON}" main.py process-issues --config "${CONFIG_PATH}" --dry-run --verbose --continue-on-error

# Sync outputs from default directories into the stamped folder if they exist
if [[ -d "artifacts/staging/outputs" ]]; then
  rsync -a "artifacts/staging/outputs/" "${OUTPUT_DIR}/" || true
fi
if [[ -d "artifacts/staging/telemetry" ]]; then
  rsync -a "artifacts/staging/telemetry/" "${TELEMETRY_DIR}/" || true
fi

echo "[${STAMP}] Staging run complete. Logs at ${LOG_DIR}"