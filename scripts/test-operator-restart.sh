#!/usr/bin/env bash
set -Eeuo pipefail

readonly CONTEXT="predictive-hpa"
readonly APP_NAMESPACE="predictive-hpa-demo"
readonly OPERATOR_NAMESPACE="phpa-system"
readonly OPERATOR_DEPLOYMENT="predictive-horizontal-pod-autoscaler"
readonly PHPA_NAME="house-price-api"
readonly CONFIGMAP_NAME="predictive-horizontal-pod-autoscaler-${PHPA_NAME}-data"
readonly HA_REPLICAS="${PHPA_HA_REPLICAS:-2}"

kube() {
  kubectl --context "${CONTEXT}" "$@"
}

kube scale deployment "${OPERATOR_DEPLOYMENT}" --namespace "${OPERATOR_NAMESPACE}" --replicas "${HA_REPLICAS}"
kube rollout status deployment/"${OPERATOR_DEPLOYMENT}" --namespace "${OPERATOR_NAMESPACE}" --timeout=180s

checkpoint_samples=$(kube get configmap "${CONFIGMAP_NAME}" --namespace "${APP_NAMESPACE}" -o json | jq -r \
  '.data.data | fromjson | .modelHistories["house-price-online"].onlineLinearState.samplesSeen // 0')
if (( checkpoint_samples < 1 )); then
  echo "No checkpointed OnlineLinear samples are available yet." >&2
  exit 1
fi

kube rollout restart deployment/"${OPERATOR_DEPLOYMENT}" --namespace "${OPERATOR_NAMESPACE}"
kube rollout status deployment/"${OPERATOR_DEPLOYMENT}" --namespace "${OPERATOR_NAMESPACE}" --timeout=180s

for _ in $(seq 1 24); do
  current_samples=$(kube get phpa "${PHPA_NAME}" --namespace "${APP_NAMESPACE}" -o json | jq -r \
    '.status.modelStatuses[]? | select(.name == "house-price-online") | .samplesSeen // 0')
  if [[ -n "${current_samples}" ]] && (( current_samples > checkpoint_samples )); then
    lease_holder=$(kube get leases --namespace "${OPERATOR_NAMESPACE}" -o json | jq -r \
      '.items[] | select(.metadata.name | contains("a07591f8")) | .spec.holderIdentity // empty' | head -1)
    if [[ -z "${lease_holder}" ]]; then
      echo "Leader-election Lease has no holder." >&2
      exit 1
    fi
    echo "Restart recovery passed: checkpoint=${checkpoint_samples}, resumed=${current_samples}, leader=${lease_holder}"
    exit 0
  fi
  sleep 5
done

echo "OnlineLinear did not resume from checkpoint within 120 seconds." >&2
exit 1
