#!/usr/bin/env bash
set -Eeuo pipefail

readonly PROFILE="predictive-hpa"
readonly KUBERNETES_VERSION="v1.26.15"
readonly KIC_BASE_IMAGE="gcr.io/k8s-minikube/kicbase@sha256:eb4fec00e8ad70adf8e6436f195cc429825ffb85f95afcdb5d8d9deb576f3e93"
readonly LOCAL_KIC_BASE_IMAGE="predictive-hpa-kicbase:v0.0.50"

base_image_args=()
if docker image inspect "${KIC_BASE_IMAGE}" >/dev/null 2>&1; then
  docker tag "${KIC_BASE_IMAGE}" "${LOCAL_KIC_BASE_IMAGE}"
  base_image_args=(--base-image "${LOCAL_KIC_BASE_IMAGE}")
fi

minikube start \
  --profile "${PROFILE}" \
  --driver docker \
  --container-runtime containerd \
  --kubernetes-version "${KUBERNETES_VERSION}" \
  --cpus 2 \
  --memory 4096 \
  --ports "127.0.0.1:8000:30080" \
  "${base_image_args[@]}" \
  --force \
  --keep-context

minikube addons enable metrics-server --profile "${PROFILE}"
minikube --profile "${PROFILE}" kubectl -- \
  --context "${PROFILE}" \
  patch deployment metrics-server --namespace kube-system --type=json \
  --patch='[{"op":"replace","path":"/spec/template/spec/containers/0/args/4","value":"--metric-resolution=15s"}]'
minikube --profile "${PROFILE}" kubectl -- \
  --context "${PROFILE}" \
  rollout status deployment/metrics-server --namespace kube-system --timeout=180s

for _ in $(seq 1 36); do
  if minikube --profile "${PROFILE}" kubectl -- \
    --context "${PROFILE}" top nodes >/dev/null 2>&1; then
    echo "Metrics Server is ready."
    exit 0
  fi
  sleep 5
done

echo "Metrics Server did not become ready within 180 seconds." >&2
exit 1
