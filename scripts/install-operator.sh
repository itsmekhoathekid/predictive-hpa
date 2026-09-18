#!/usr/bin/env bash
set -Eeuo pipefail

readonly CONTEXT="predictive-hpa"
readonly APP_NAMESPACE="predictive-hpa-demo"
readonly OPERATOR_NAMESPACE="river-phpa-system"
readonly RELEASE="kopf-river-phpa"
readonly VERSION="v0.1.0"
readonly IMAGE="ghcr.io/itsmekhoathekid/kopf-river-phpa:${VERSION}"
readonly SOURCE_URL="https://github.com/itsmekhoathekid/kopf-river-phpa"
readonly SOURCE_COMMIT="3e936b3da02b9e5281ea7dfd7b46afaad1c91fa5"
readonly SOURCE_SHA256="4de15c8967d23327804a3c1799a1db45a6515b016c0b5678b659decfe6bb0ae3"

build_dir=$(mktemp -d)
trap 'find "${build_dir}" -mindepth 1 -delete; rmdir "${build_dir}"' EXIT
archive_path="${build_dir}/operator.tar.gz"
source_dir="${build_dir}/source"
mkdir -p "${source_dir}"

if [[ -n "${RIVER_PHPA_SOURCE_DIR:-}" ]]; then
  if [[ ! -d "${RIVER_PHPA_SOURCE_DIR}/charts/kopf-river-phpa" ]]; then
    echo "RIVER_PHPA_SOURCE_DIR does not contain the operator Helm chart." >&2
    exit 1
  fi
  tar --exclude=.git --create --file=- --directory "${RIVER_PHPA_SOURCE_DIR}" . | \
    tar --extract --file=- --directory "${source_dir}"
else
  curl --fail --silent --show-error --location \
    "${SOURCE_URL}/archive/${SOURCE_COMMIT}.tar.gz" \
    --output "${archive_path}"
  actual_sha=$(shasum -a 256 "${archive_path}" | awk '{print $1}')
  if [[ "${actual_sha}" != "${SOURCE_SHA256}" ]]; then
    echo "Kopf River PHPA source checksum mismatch." >&2
    exit 1
  fi
  tar -xzf "${archive_path}" --strip-components=1 --directory "${source_dir}"
fi

# Ensure a previous Go PHPA installation cannot control the same Deployment.
kubectl --context "${CONTEXT}" delete phpa house-price-api \
  --namespace "${APP_NAMESPACE}" --ignore-not-found 2>/dev/null || true
if helm status predictive-horizontal-pod-autoscaler-operator \
  --kube-context "${CONTEXT}" --namespace phpa-system >/dev/null 2>&1; then
  helm uninstall predictive-horizontal-pod-autoscaler-operator \
    --kube-context "${CONTEXT}" --namespace phpa-system
fi

helm upgrade --install "${RELEASE}" "${source_dir}/charts/kopf-river-phpa" \
  --kube-context "${CONTEXT}" \
  --namespace "${OPERATOR_NAMESPACE}" \
  --create-namespace \
  --set "image.repository=ghcr.io/itsmekhoathekid/kopf-river-phpa" \
  --set "image.tag=${VERSION}" \
  --set "image.pullPolicy=IfNotPresent" \
  --wait \
  --timeout 10m

kubectl --context "${CONTEXT}" rollout status \
  deployment/kopf-river-phpa-kopf-river-phpa \
  --namespace "${OPERATOR_NAMESPACE}" \
  --timeout=300s

echo "Installed ${IMAGE} from ${SOURCE_COMMIT}."
