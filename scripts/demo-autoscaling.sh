#!/usr/bin/env bash
set -Eeuo pipefail

readonly PROFILE="predictive-hpa"
readonly CONTEXT="predictive-hpa"
readonly NAMESPACE="predictive-hpa-demo"
readonly DEPLOYMENT="house-price-api"
readonly HOST="http://127.0.0.1:8000"
readonly USERS="${LOCUST_USERS:-150}"
readonly SPAWN_RATE="${LOCUST_SPAWN_RATE:-25}"
readonly RUN_TIME="${LOCUST_RUN_TIME:-5m}"
readonly REQUIRED_MAX_REPLICAS=8

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
artifact_dir="${project_root}/.artifacts"
mkdir -p "${artifact_dir}"
sample_file="${artifact_dir}/autoscaling-demo.csv"
locust_stats_prefix="${artifact_dir}/locust"
locust_pid=""

cleanup() {
  if [[ -n "${locust_pid}" ]] && kill -0 "${locust_pid}" 2>/dev/null; then
    kill "${locust_pid}"
    wait "${locust_pid}" 2>/dev/null || true
  fi
}
trap cleanup EXIT

kube() {
  kubectl --context "${CONTEXT}" "$@"
}

replica_count() {
  local count
  count=$(kube get deployment "${DEPLOYMENT}" --namespace "${NAMESPACE}" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)
  echo "${count:-0}"
}

curl --fail --silent "${HOST}/healthz" >/dev/null
echo "timestamp,ready_replicas,reactive_replicas,desired_replicas,model_ready,samples_seen,updates_applied,pending_samples,prediction,mae,last_checkpoint" >"${sample_file}"
echo "Starting Locust immediately; current River PHPA history and replica count are preserved."

LOCUST_USERS="${USERS}" LOCUST_SPAWN_RATE="${SPAWN_RATE}" uv run --group load locust \
  --locustfile "${project_root}/loadtest/locustfile.py" \
  --headless \
  --run-time "${RUN_TIME}" \
  --csv "${locust_stats_prefix}" \
  --csv-full-history \
  --host "${HOST}" &
locust_pid=$!

max_replicas=$(replica_count)
while kill -0 "${locust_pid}" 2>/dev/null; do
  current=$(replica_count)
  if (( current > max_replicas )); then
    max_replicas=${current}
  fi
  timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  phpa_json=$(kube get rphpa house-price-api --namespace "${NAMESPACE}" -o json)
  status_fields=$(jq -r '
    (.status.modelStatuses[]? | select(.name == "house-price-online")) as $model |
    [
      (.status.reactiveReplicas // 0),
      (.status.desiredReplicas // 0),
      ($model.ready // false),
      ($model.samplesSeen // 0),
      ($model.updatesApplied // 0),
      ($model.pendingSamples // 0),
      ($model.lastPrediction // 0),
      ($model.meanAbsoluteError // 0),
      ($model.lastCheckpointTime // "")
    ] | @csv
  ' <<<"${phpa_json}")
  if [[ -z "${status_fields}" ]]; then
    status_fields='0,0,false,0,0,0,0,0,""'
  fi
  echo "${timestamp},${current},${status_fields}" | tee -a "${sample_file}"
  kube top pods --namespace "${NAMESPACE}" 2>/dev/null || true
  sleep 10
done

set +e
wait "${locust_pid}"
locust_status=$?
set -e
locust_pid=""

if (( locust_status != 0 )); then
  echo "Locust failed with exit code ${locust_status}." >&2
  exit "${locust_status}"
fi
if (( max_replicas < REQUIRED_MAX_REPLICAS )); then
  echo "Autoscaling failed: expected ${REQUIRED_MAX_REPLICAS}, observed ${max_replicas}." >&2
  exit 1
fi

echo "Load test passed: observed up to ${max_replicas} ready replicas."
echo "Samples: ${sample_file}"

summary=$(awk -F, '
  NR > 1 {
    pod_seconds += $2 * 10
    if ($2 < $3) under_seconds += 10
  }
  END {
    printf "pod_minutes=%.2f under_provisioned_seconds=%d", pod_seconds / 60, under_seconds
  }
' "${sample_file}")
p95=$(awk -F, '
  NR == 1 {
    for (i = 1; i <= NF; i++) if ($i == "95%") column = i
  }
  $2 == "Aggregated" && column { value = $column }
  END { print value }
' "${locust_stats_prefix}_stats.csv")
echo "Benchmark: ${summary} p95_ms=${p95:-unavailable}"
