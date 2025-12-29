#!/usr/bin/env bash
set -euo pipefail

# Deploy script for worker_llm_client (Cloud Functions gen2, Firestore trigger).
# Follows the gcp-functions-gen2-python-deploy playbook.
#
# Usage:
#   export PROJECT_ID="<PROJECT_ID>"
#   export REGION="<REGION>"
#   export FUNCTION_NAME="worker_llm_client"
#   export RUNTIME="python313"
#   export SOURCE_DIR="."
#   export TRIGGER_KIND="firestore"
#   export FIRESTORE_DB="<DB_ID>"
#   export FIRESTORE_NAMESPACE="(default)"
#   export FIRESTORE_TRIGGER_EVENT_TYPE="google.cloud.firestore.document.v1.updated"
#   export FIRESTORE_TRIGGER_DOCUMENT_PATH="flow_runs/{runId}"
#   export RUNTIME_SA_EMAIL="<RUNTIME_SA_EMAIL>"
#   export TRIGGER_SA_EMAIL="<TRIGGER_SA_EMAIL>"   # optional; defaults to runtime SA
#   export ENV_VARS_MODE="inline"                   # file|inline
#   export ENV_VARS_INLINE="KEY=VALUE,KEY=VALUE"    # required if inline
#   export SECRET_ENV_VARS="KEY=projects/.../secrets/<NAME>:<VERSION>"  # optional
#   export CONFIRM_TRIGGER_UNCHANGED=true            # required for update deploys unless ALLOW_TRIGGER_CHANGE=true
#   ./scripts/deploy_dev.sh

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

require_var() {
  local name="$1"
  local val="${!name:-}"
  if [[ -z "${val}" ]]; then
    fail "Missing ${name}"
  fi
}

require_var PROJECT_ID
require_var REGION
require_var FUNCTION_NAME

RUNTIME="${RUNTIME:-python313}"
SOURCE_DIR="${SOURCE_DIR:-.}"
TRIGGER_KIND="${TRIGGER_KIND:-firestore}"

if [[ "${TRIGGER_KIND}" != "firestore" ]]; then
  fail "Only TRIGGER_KIND=firestore is supported by this script"
fi

require_var FIRESTORE_DB
FIRESTORE_NAMESPACE="${FIRESTORE_NAMESPACE:-(default)}"
FIRESTORE_TRIGGER_EVENT_TYPE="${FIRESTORE_TRIGGER_EVENT_TYPE:-google.cloud.firestore.document.v1.updated}"
FIRESTORE_TRIGGER_DOCUMENT_PATH="${FIRESTORE_TRIGGER_DOCUMENT_PATH:-flow_runs/{runId}}"

require_var RUNTIME_SA_EMAIL
TRIGGER_SA_EMAIL="${TRIGGER_SA_EMAIL:-${RUNTIME_SA_EMAIL}}"

ENV_VARS_MODE="${ENV_VARS_MODE:-inline}"
ENV_VARS_INLINE="${ENV_VARS_INLINE:-}"
ENV_VARS_FILE="${ENV_VARS_FILE:-}"
SECRET_ENV_VARS="${SECRET_ENV_VARS:-}"

if [[ "${ENV_VARS_MODE}" == "file" ]]; then
  [[ -n "${ENV_VARS_FILE}" ]] || fail "ENV_VARS_FILE is required when ENV_VARS_MODE=file"
  ENV_FLAGS=("--env-vars-file" "${ENV_VARS_FILE}")
elif [[ "${ENV_VARS_MODE}" == "inline" ]]; then
  [[ -n "${ENV_VARS_INLINE}" ]] || fail "ENV_VARS_INLINE is required when ENV_VARS_MODE=inline"
  ENV_FLAGS=("--set-env-vars" "${ENV_VARS_INLINE}")
else
  fail "ENV_VARS_MODE must be 'file' or 'inline'"
fi

SECRET_FLAGS=()
if [[ -n "${SECRET_ENV_VARS}" ]]; then
  SECRET_FLAGS=("--set-secrets" "${SECRET_ENV_VARS}")
fi

command -v gcloud >/dev/null 2>&1 || fail "gcloud is not installed"

# Source packaging checks (playbook Section 4.2)
[[ -f "${SOURCE_DIR}/main.py" ]] || fail "Missing ${SOURCE_DIR}/main.py"
[[ -f "${SOURCE_DIR}/.gcloudignore" ]] || fail "Missing ${SOURCE_DIR}/.gcloudignore"
if [[ ! -f "${SOURCE_DIR}/requirements.txt" ]]; then
  fail "Missing ${SOURCE_DIR}/requirements.txt (confirm custom dependency mechanism before deploy)"
fi

# Derive ENTRY_POINT from main.py unless provided explicitly (playbook Section 4.3)
if [[ -z "${ENTRY_POINT:-}" ]]; then
  ENTRY_POINT="$(
    python3 - <<'PY'
import re
from pathlib import Path

path = Path("main.py")
text = path.read_text(encoding="utf-8")
lines = text.splitlines()

entrypoints = []
for i, line in enumerate(lines):
    if "@functions_framework.cloud_event" in line or "@functions_framework.http" in line:
        for j in range(i + 1, len(lines)):
            m = re.match(r"\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", lines[j])
            if m:
                entrypoints.append(m.group(1))
                break

if len(entrypoints) == 1:
    print(entrypoints[0])
    raise SystemExit(0)

raise SystemExit(2)
PY
  )" || fail "Unable to derive ENTRY_POINT; set ENTRY_POINT explicitly"
fi

# Decide deploy mode (playbook Section 2)
if gcloud functions describe "${FUNCTION_NAME}" \
  --gen2 \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format="value(name)" \
  >/dev/null 2>&1; then
  DEPLOY_MODE="update"
else
  DEPLOY_MODE="first"
fi

# Set gcloud project (playbook Section 4.1)
gcloud config set project "${PROJECT_ID}"

if [[ "${DEPLOY_MODE}" == "first" ]]; then
  # Enable APIs (playbook Section 4.4)
  gcloud services enable \
    cloudfunctions.googleapis.com \
    run.googleapis.com \
    eventarc.googleapis.com \
    cloudbuild.googleapis.com \
    artifactregistry.googleapis.com \
    logging.googleapis.com \
    firestore.googleapis.com \
    storage.googleapis.com \
    secretmanager.googleapis.com \
    --project "${PROJECT_ID}"
fi

# Firestore DB region alignment check (playbook Section 4.5)
DB_JSON="$(gcloud firestore databases list --project "${PROJECT_ID}" --format=json)"
export DB_JSON FIRESTORE_DB REGION
python3 - <<'PY'
import json
import os
import sys

data = json.loads(os.environ["DB_JSON"])
want = os.environ["FIRESTORE_DB"]
region = os.environ["REGION"]

found = False
for item in data:
    name = item.get("name", "")
    location = item.get("locationId", "")
    if name.endswith(f"/databases/{want}"):
        found = True
        if location != region:
            print(f"Firestore DB location mismatch: {location} != {region}", file=sys.stderr)
            sys.exit(2)

if not found:
    print(f"Firestore DB not found: {want}", file=sys.stderr)
    sys.exit(2)
PY

if [[ "${DEPLOY_MODE}" == "update" ]]; then
  if [[ "${ALLOW_TRIGGER_CHANGE:-false}" != "true" ]]; then
    echo "Update mode: review existing trigger config before proceeding:"
    gcloud functions describe "${FUNCTION_NAME}" \
      --gen2 \
      --project "${PROJECT_ID}" \
      --region "${REGION}" \
      --format="yaml(eventTrigger)"
    if [[ "${CONFIRM_TRIGGER_UNCHANGED:-false}" != "true" ]]; then
      fail "Set CONFIRM_TRIGGER_UNCHANGED=true (or ALLOW_TRIGGER_CHANGE=true) to proceed"
    fi
  fi
fi

# Deploy (playbook Section 4.8.1)
gcloud functions deploy "${FUNCTION_NAME}" \
  --gen2 \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --runtime "${RUNTIME}" \
  --source "${SOURCE_DIR}" \
  --entry-point "${ENTRY_POINT}" \
  --service-account "${RUNTIME_SA_EMAIL}" \
  --trigger-service-account "${TRIGGER_SA_EMAIL}" \
  --trigger-location "${REGION}" \
  --trigger-event-filters "type=${FIRESTORE_TRIGGER_EVENT_TYPE}" \
  --trigger-event-filters "database=${FIRESTORE_DB}" \
  --trigger-event-filters "namespace=${FIRESTORE_NAMESPACE}" \
  --trigger-event-filters-path-pattern "document=${FIRESTORE_TRIGGER_DOCUMENT_PATH}" \
  "${ENV_FLAGS[@]}" \
  "${SECRET_FLAGS[@]}"

# Confirm deploy status (playbook Section 4.10/5.4)
gcloud functions describe "${FUNCTION_NAME}" \
  --gen2 \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format="value(state,serviceConfig.revision,updateTime)"
