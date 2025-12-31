#!/usr/bin/env bash
set -euo pipefail

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

info() {
  echo "INFO: $*"
}

usage() {
  cat <<'EOF'
Usage:
  scripts/deploy_prod.sh [--env-file PATH]

Defaults:
  --env-file .env.prod.local

Notes:
  - Smoke verification runs only if APPROVE_SMOKE_VERIFY=true in the env file.
  - Do not commit real identifiers/secrets into the repo; keep them in .env.prod.local (ignored).
EOF
}

ENV_FILE=".env.prod.local"
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  usage
  exit 0
fi
if [[ "${1:-}" == "--env-file" ]]; then
  ENV_FILE="${2:-}"
  [[ -n "${ENV_FILE}" ]] || fail "--env-file requires a path"
fi

[[ -f "${ENV_FILE}" ]] || fail "Missing env file: ${ENV_FILE}"

set -a
# shellcheck disable=SC1090
source "${ENV_FILE}"
set +a

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
require_var FIRESTORE_DB
require_var RUNTIME_SA_EMAIL
require_var ARTIFACTS_BUCKET
require_var FLOW_RUNS_COLLECTION

ENV_VARS_MODE="${ENV_VARS_MODE:-inline}"
ENV_VARS_FILE="${ENV_VARS_FILE:-}"
ENV_VARS_INLINE="${ENV_VARS_INLINE:-}"
SECRET_ENV_VARS="${SECRET_ENV_VARS:-}"
APPROVE_SMOKE_VERIFY="${APPROVE_SMOKE_VERIFY:-false}"

ARTIFACTS_PREFIX="${ARTIFACTS_PREFIX:-}"
ARTIFACTS_DRY_RUN="${ARTIFACTS_DRY_RUN:-false}"
GEMINI_TIMEOUT_SECONDS="${GEMINI_TIMEOUT_SECONDS:-600}"
FINALIZE_BUDGET_SECONDS="${FINALIZE_BUDGET_SECONDS:-120}"
INVOCATION_TIMEOUT_SECONDS="${INVOCATION_TIMEOUT_SECONDS:-780}"
LOG_LEVEL="${LOG_LEVEL:-INFO}"

if [[ "${ENV_VARS_MODE}" == "file" ]]; then
  [[ -n "${ENV_VARS_FILE}" ]] || fail "ENV_VARS_FILE is required when ENV_VARS_MODE=file"
else
  if [[ -z "${ENV_VARS_INLINE}" ]]; then
    ENV_VARS_INLINE="GCP_PROJECT=${PROJECT_ID},GCP_REGION=${REGION},FIRESTORE_DATABASE=${FIRESTORE_DB},FLOW_RUNS_COLLECTION=${FLOW_RUNS_COLLECTION},ARTIFACTS_BUCKET=${ARTIFACTS_BUCKET},ARTIFACTS_PREFIX=${ARTIFACTS_PREFIX},ARTIFACTS_DRY_RUN=${ARTIFACTS_DRY_RUN},GEMINI_TIMEOUT_SECONDS=${GEMINI_TIMEOUT_SECONDS},FINALIZE_BUDGET_SECONDS=${FINALIZE_BUDGET_SECONDS},INVOCATION_TIMEOUT_SECONDS=${INVOCATION_TIMEOUT_SECONDS},LOG_LEVEL=${LOG_LEVEL}"
  fi
fi

export CONFIRM_TRIGGER_UNCHANGED=true
export PROJECT_ID REGION FUNCTION_NAME FIRESTORE_DB RUNTIME_SA_EMAIL
export ENV_VARS_MODE ENV_VARS_FILE ENV_VARS_INLINE SECRET_ENV_VARS

info "Deploying ${FUNCTION_NAME} to ${PROJECT_ID}/${REGION}..."
scripts/deploy_dev.sh

info "Deploy status:"
gcloud functions describe "${FUNCTION_NAME}" \
  --gen2 \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --format="value(state,serviceConfig.revision,updateTime)"

if [[ "${APPROVE_SMOKE_VERIFY}" != "true" ]]; then
  info "Smoke verification skipped (APPROVE_SMOKE_VERIFY!=true)."
  exit 0
fi

require_var SMOKE_POS_RUN_ID
require_var SMOKE_POS_STEP_ID
require_var SMOKE_POS_TIMEFRAME
require_var SMOKE_NEG_RUN_ID
require_var SMOKE_NEG_STEP_ID

SMOKE_NEG_SCHEMA_ID="${SMOKE_NEG_SCHEMA_ID:-llm_report_output_smoke_invalid}"
SMOKE_NEG_SCHEMA_KIND="${SMOKE_NEG_SCHEMA_KIND:-LLM_REPORT_OUTPUT}"
SMOKE_NEG_SCHEMA_DESC="${SMOKE_NEG_SCHEMA_DESC:-Invalid schema for smoke negative scenario.}"
SMOKE_CLEANUP_GCS="${SMOKE_CLEANUP_GCS:-true}"

ACCESS_TOKEN="$(gcloud auth print-access-token)"
FIRESTORE_BASE="https://firestore.googleapis.com/v1/projects/${PROJECT_ID}/databases/${FIRESTORE_DB}/documents"

tmpdir="$(mktemp -d)"
cleanup() {
  rm -rf "${tmpdir}"
}
trap cleanup EXIT

firestore_get() {
  local run_id="$1"
  curl -s -H "Authorization: Bearer ${ACCESS_TOKEN}" \
    "${FIRESTORE_BASE}/${FLOW_RUNS_COLLECTION}/${run_id}" \
    -o "${tmpdir}/${run_id}.json"
}

build_restore_patch() {
  local run_id="$1"
  local step_id="$2"
  python3 - <<'PY' >"${tmpdir}/${run_id}_${step_id}_restore.json"
import json, os, sys

run_id = os.environ["RUN_ID"]
step_id = os.environ["STEP_ID"]
doc = json.load(open(os.environ["DOC_PATH"]))
fields = doc.get("fields", {})
steps = fields.get("steps", {}).get("mapValue", {}).get("fields", {})
step = steps.get(step_id, {}).get("mapValue", {}).get("fields", {})
status = step.get("status")
error = step.get("error")
schema_id = None
llm_profile = (
    step.get("inputs", {})
        .get("mapValue", {})
        .get("fields", {})
        .get("llm", {})
        .get("mapValue", {})
        .get("fields", {})
        .get("llmProfile", {})
        .get("mapValue", {})
        .get("fields", {})
)
structured = llm_profile.get("structuredOutput", {}).get("mapValue", {}).get("fields", {})
schema_field = structured.get("schemaId")
if schema_field and "stringValue" in schema_field:
    schema_id = schema_field["stringValue"]

def fs_str(v):
    return {"stringValue": v}

def fs_null():
    return {"nullValue": None}

error_value = error if isinstance(error, dict) else fs_null()
status_value = status if isinstance(status, dict) else fs_str("READY")

fields_out = {
    "steps": {
        "mapValue": {
            "fields": {
                step_id: {
                    "mapValue": {
                        "fields": {
                            "status": status_value,
                            "error": error_value,
                        }
                    }
                }
            }
        }
    }
}

if schema_id:
    fields_out["steps"]["mapValue"]["fields"][step_id]["mapValue"]["fields"]["inputs"] = {
        "mapValue": {
            "fields": {
                "llm": {
                    "mapValue": {
                        "fields": {
                            "llmProfile": {
                                "mapValue": {
                                    "fields": {
                                        "structuredOutput": {
                                            "mapValue": {
                                                "fields": {"schemaId": fs_str(schema_id)}
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

json.dump({"fields": fields_out}, sys.stdout)
PY
}

firestore_patch() {
  local run_id="$1"
  local update_mask="$2"
  local payload="$3"
  curl -s -X PATCH -H "Authorization: Bearer ${ACCESS_TOKEN}" -H "Content-Type: application/json" \
    "${FIRESTORE_BASE}/${FLOW_RUNS_COLLECTION}/${run_id}?${update_mask}" \
    --data-binary "@${payload}" \
    -o "${tmpdir}/${run_id}_patch_response.json"
}

extract_step_status_code() {
  local doc_path="$1"
  local step_id="$2"
  python3 - "$doc_path" "$step_id" <<'PY'
import json, sys
doc = json.load(open(sys.argv[1]))
step_id = sys.argv[2]
step = doc.get("fields", {}).get("steps", {}).get("mapValue", {}).get("fields", {}).get(step_id, {})
fields = step.get("mapValue", {}).get("fields", {})
status = fields.get("status", {}).get("stringValue")
error = fields.get("error", {}).get("mapValue", {}).get("fields", {})
code = error.get("code", {}).get("stringValue")
print(status or "")
print(code or "")
PY
}

wait_for_step_status() {
  local run_id="$1"
  local step_id="$2"
  local timeout_secs="${3:-60}"
  local interval_secs="${4:-5}"
  local deadline=$((SECONDS + timeout_secs))
  local status=""
  local code=""
  while true; do
    firestore_get "${run_id}"
    readarray -t result < <(extract_step_status_code "${tmpdir}/${run_id}.json" "${step_id}")
    status="${result[0]:-}"
    code="${result[1]:-}"
    if [[ "${status}" == "SUCCEEDED" || "${status}" == "FAILED" ]]; then
      echo "${status}"
      echo "${code}"
      return 0
    fi
    if (( SECONDS >= deadline )); then
      echo "${status}"
      echo "${code}"
      return 0
    fi
    sleep "${interval_secs}"
  done
}

info "Smoke (positive) using ${SMOKE_POS_RUN_ID}/${SMOKE_POS_STEP_ID}..."
firestore_get "${SMOKE_POS_RUN_ID}"
RUN_ID="${SMOKE_POS_RUN_ID}" STEP_ID="${SMOKE_POS_STEP_ID}" DOC_PATH="${tmpdir}/${SMOKE_POS_RUN_ID}.json" \
  build_restore_patch "${SMOKE_POS_RUN_ID}" "${SMOKE_POS_STEP_ID}"

UPDATED_AT="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
STEP_ID="${SMOKE_POS_STEP_ID}" UPDATED_AT="${UPDATED_AT}" \
python3 - <<'PY' >"${tmpdir}/pos_patch.json"
import json, os
def fs_ts(v): return {"timestampValue": v}
def fs_str(v): return {"stringValue": v}
def fs_null(): return {"nullValue": None}
step_id=os.environ["STEP_ID"]
fields={
  "updatedAt": fs_ts(os.environ["UPDATED_AT"]),
  "steps": {"mapValue": {"fields": {step_id: {"mapValue": {"fields": {
    "status": fs_str("READY"),
    "error": fs_null(),
  }}}}}}
}
print(json.dumps({"fields": fields}))
PY
UPDATE_MASK="updateMask.fieldPaths=updatedAt&updateMask.fieldPaths=steps.${SMOKE_POS_STEP_ID}.status&updateMask.fieldPaths=steps.${SMOKE_POS_STEP_ID}.error"
STEP_ID="${SMOKE_POS_STEP_ID}" UPDATED_AT="${UPDATED_AT}" \
  firestore_patch "${SMOKE_POS_RUN_ID}" "${UPDATE_MASK}" "${tmpdir}/pos_patch.json"

readarray -t pos_status < <(wait_for_step_status "${SMOKE_POS_RUN_ID}" "${SMOKE_POS_STEP_ID}" 90 6)
POS_STATUS="${pos_status[0]:-}"
POS_CODE="${pos_status[1]:-}"

if [[ "${POS_STATUS}" == "SUCCEEDED" ]]; then
  info "Smoke positive: SUCCEEDED"
  POS_OK=true
else
  info "Smoke positive: FAILED (status=${POS_STATUS} code=${POS_CODE})"
  POS_OK=false
fi

if [[ "${SMOKE_CLEANUP_GCS}" == "true" ]]; then
  prefix="${ARTIFACTS_PREFIX#/}"
  prefix="${prefix%/}"
  if [[ -n "${prefix}" ]]; then
    REPORT_URI="gs://${ARTIFACTS_BUCKET}/${prefix}/${SMOKE_POS_RUN_ID}/${SMOKE_POS_TIMEFRAME}/${SMOKE_POS_STEP_ID}.json"
  else
    REPORT_URI="gs://${ARTIFACTS_BUCKET}/${SMOKE_POS_RUN_ID}/${SMOKE_POS_TIMEFRAME}/${SMOKE_POS_STEP_ID}.json"
  fi
  info "Cleanup report artifact: ${REPORT_URI}"
  gsutil rm -f "${REPORT_URI}" >/dev/null 2>&1 || true
fi

info "Restore positive flow_run fields..."
UPDATE_MASK="updateMask.fieldPaths=steps.${SMOKE_POS_STEP_ID}.status&updateMask.fieldPaths=steps.${SMOKE_POS_STEP_ID}.error"
firestore_patch "${SMOKE_POS_RUN_ID}" "${UPDATE_MASK}" "${tmpdir}/${SMOKE_POS_RUN_ID}_${SMOKE_POS_STEP_ID}_restore.json"

info "Smoke (negative invalid schema) using ${SMOKE_NEG_RUN_ID}/${SMOKE_NEG_STEP_ID}..."
firestore_get "${SMOKE_NEG_RUN_ID}"
RUN_ID="${SMOKE_NEG_RUN_ID}" STEP_ID="${SMOKE_NEG_STEP_ID}" DOC_PATH="${tmpdir}/${SMOKE_NEG_RUN_ID}.json" \
  build_restore_patch "${SMOKE_NEG_RUN_ID}" "${SMOKE_NEG_STEP_ID}"

CREATED_AT="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
SCHEMA_ID="${SMOKE_NEG_SCHEMA_ID}" SCHEMA_KIND="${SMOKE_NEG_SCHEMA_KIND}" \
SCHEMA_DESC="${SMOKE_NEG_SCHEMA_DESC}" CREATED_AT="${CREATED_AT}" \
python3 - <<'PY' >"${tmpdir}/invalid_schema.json"
import json, os, hashlib
def fs_str(v): return {"stringValue": v}
def fs_ts(v): return {"timestampValue": v}
def fs_bool(v): return {"booleanValue": bool(v)}

schema = {
  "type": "object",
  "additionalProperties": False,
  "required": ["details"],
  "properties": {"details": {"type": "object", "additionalProperties": True}},
}
payload = json.dumps(schema, sort_keys=True, separators=(",", ":")).encode("utf-8")
sha256 = hashlib.sha256(payload).hexdigest()

fields = {
  "schemaId": fs_str(os.environ["SCHEMA_ID"]),
  "kind": fs_str(os.environ["SCHEMA_KIND"]),
  "description": fs_str(os.environ["SCHEMA_DESC"]),
  "isActive": fs_bool(True),
  "createdAt": fs_ts(os.environ["CREATED_AT"]),
  "sha256": fs_str(sha256),
  "jsonSchema": {"mapValue": {"fields": {
    "type": fs_str(schema["type"]),
    "additionalProperties": {"booleanValue": schema["additionalProperties"]},
    "required": {"arrayValue": {"values": [fs_str(v) for v in schema["required"]]}},
    "properties": {"mapValue": {"fields": {
      "details": {"mapValue": {"fields": {
        "type": fs_str("object"),
        "additionalProperties": {"booleanValue": True},
      }}}
    }}},
  }}}
}
print(json.dumps({"fields": fields}))
PY

curl -s -X PATCH -H "Authorization: Bearer ${ACCESS_TOKEN}" -H "Content-Type: application/json" \
  "${FIRESTORE_BASE}/llm_schemas/${SMOKE_NEG_SCHEMA_ID}" \
  --data-binary "@${tmpdir}/invalid_schema.json" >/dev/null

UPDATED_AT="$(date -u +%Y-%m-%dT%H:%M:%S.%NZ)"
STEP_ID="${SMOKE_NEG_STEP_ID}" SCHEMA_ID="${SMOKE_NEG_SCHEMA_ID}" UPDATED_AT="${UPDATED_AT}" \
python3 - <<'PY' >"${tmpdir}/neg_patch.json"
import json, os
def fs_ts(v): return {"timestampValue": v}
def fs_str(v): return {"stringValue": v}
def fs_null(): return {"nullValue": None}
step_id=os.environ["STEP_ID"]
schema_id=os.environ["SCHEMA_ID"]
fields = {
    "updatedAt": fs_ts(os.environ["UPDATED_AT"]),
    "steps": {
        "mapValue": {
            "fields": {
                step_id: {
                    "mapValue": {
                        "fields": {
                            "status": fs_str("READY"),
                            "error": fs_null(),
                            "inputs": {
                                "mapValue": {
                                    "fields": {
                                        "llm": {
                                            "mapValue": {
                                                "fields": {
                                                    "llmProfile": {
                                                        "mapValue": {
                                                            "fields": {
                                                                "structuredOutput": {
                                                                    "mapValue": {
                                                                        "fields": {
                                                                            "schemaId": fs_str(schema_id)
                                                                        }
                                                                    }
                                                                }
                                                            }
                                                        }
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
print(json.dumps({"fields": fields}))
PY
UPDATE_MASK="updateMask.fieldPaths=updatedAt&updateMask.fieldPaths=steps.${SMOKE_NEG_STEP_ID}.status&updateMask.fieldPaths=steps.${SMOKE_NEG_STEP_ID}.error&updateMask.fieldPaths=steps.${SMOKE_NEG_STEP_ID}.inputs.llm.llmProfile.structuredOutput.schemaId"
firestore_patch "${SMOKE_NEG_RUN_ID}" "${UPDATE_MASK}" "${tmpdir}/neg_patch.json"

readarray -t neg_status < <(wait_for_step_status "${SMOKE_NEG_RUN_ID}" "${SMOKE_NEG_STEP_ID}" 90 6)
NEG_STATUS="${neg_status[0]:-}"
NEG_CODE="${neg_status[1]:-}"

if [[ "${NEG_STATUS}" == "FAILED" && "${NEG_CODE}" == "LLM_PROFILE_INVALID" ]]; then
  info "Smoke negative: FAILED with LLM_PROFILE_INVALID"
  NEG_OK=true
else
  info "Smoke negative: FAILED check (status=${NEG_STATUS} code=${NEG_CODE})"
  NEG_OK=false
fi

info "Cleanup negative artifacts..."
curl -s -X DELETE -H "Authorization: Bearer ${ACCESS_TOKEN}" \
  "${FIRESTORE_BASE}/llm_schemas/${SMOKE_NEG_SCHEMA_ID}" >/dev/null || true

info "Restore negative flow_run fields..."
UPDATE_MASK="updateMask.fieldPaths=steps.${SMOKE_NEG_STEP_ID}.status&updateMask.fieldPaths=steps.${SMOKE_NEG_STEP_ID}.error&updateMask.fieldPaths=steps.${SMOKE_NEG_STEP_ID}.inputs.llm.llmProfile.structuredOutput.schemaId"
firestore_patch "${SMOKE_NEG_RUN_ID}" "${UPDATE_MASK}" "${tmpdir}/${SMOKE_NEG_RUN_ID}_${SMOKE_NEG_STEP_ID}_restore.json"

echo ""
echo "=== Smoke summary ==="
echo "positive: ${POS_OK}"
echo "negative: ${NEG_OK}"
if [[ "${POS_OK}" == "true" && "${NEG_OK}" == "true" ]]; then
  echo "SMOKE_RESULT=PASS"
  exit 0
fi
echo "SMOKE_RESULT=FAIL"
exit 2
