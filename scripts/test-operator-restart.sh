#!/usr/bin/env bash
set -Eeuo pipefail

readonly CONTEXT="predictive-hpa"
readonly APP_NAMESPACE="predictive-hpa-demo"
readonly OPERATOR_NAMESPACE="river-phpa-system"
readonly OPERATOR_DEPLOYMENT="kopf-river-phpa-kopf-river-phpa"
readonly RPHPA_NAME="house-price-api"
readonly CONFIGMAP_NAME="rphpa-${RPHPA_NAME}-state"

kube() {
  kubectl --context "${CONTEXT}" "$@"
}

checkpoint_samples=$(kube get configmap "${CONFIGMAP_NAME}" \
  --namespace "${APP_NAMESPACE}" -o json | jq -r \
  '.data["model.pkl.b64"] | length')
before_status=$(kube get rphpa "${RPHPA_NAME}" --namespace "${APP_NAMESPACE}" -o json)
before_samples=$(jq -r '.status.modelStatuses[0].samplesSeen // 0' <<<"${before_status}")
before_updates=$(jq -r '.status.modelStatuses[0].updatesApplied // 0' <<<"${before_status}")
before_pending=$(jq -r '.status.modelStatuses[0].pendingSamples // 0' <<<"${before_status}")

if (( checkpoint_samples < 1 || before_samples < 1 )); then
  echo "No checkpointed River model samples are available yet." >&2
  exit 1
fi

kube rollout restart deployment/"${OPERATOR_DEPLOYMENT}" --namespace "${OPERATOR_NAMESPACE}"
kube rollout status deployment/"${OPERATOR_DEPLOYMENT}" \
  --namespace "${OPERATOR_NAMESPACE}" --timeout=180s

for _ in $(seq 1 24); do
  current_status=$(kube get rphpa "${RPHPA_NAME}" --namespace "${APP_NAMESPACE}" -o json)
  current_samples=$(jq -r '.status.modelStatuses[0].samplesSeen // 0' <<<"${current_status}")
  current_updates=$(jq -r '.status.modelStatuses[0].updatesApplied // 0' <<<"${current_status}")
  current_pending=$(jq -r '.status.modelStatuses[0].pendingSamples // 0' <<<"${current_status}")
  if (( current_samples > before_samples && current_updates >= before_updates )); then
    echo "Restart recovery passed: samples=${before_samples}->${current_samples}, updates=${before_updates}->${current_updates}, pending=${before_pending}->${current_pending}"
    exit 0
  fi
  sleep 5
done

echo "River model did not resume from checkpoint within 120 seconds." >&2
exit 1
