#!/usr/bin/env bash
set -Eeuo pipefail

readonly PROFILE="predictive-hpa"
readonly CONTEXT="predictive-hpa"
readonly NAMESPACE="phpa-system"
readonly RELEASE="predictive-horizontal-pod-autoscaler-operator"
readonly VERSION="v0.14.0-online.1"
readonly IMAGE="itsmekhoathekid/predictive-horizontal-pod-autoscaler:${VERSION}"
readonly FORK_URL="https://github.com/itsmekhoathekid/predictive-horizontal-pod-autoscaler"

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
local_source=${PHPA_SOURCE_DIR:-"${project_root}/../predictive-horizontal-pod-autoscaler"}
node_arch=$(kubectl --context "${CONTEXT}" get node -o jsonpath='{.items[0].status.nodeInfo.architecture}')

build_dir=$(mktemp -d)
trap 'rm -rf "${build_dir}"' EXIT
archive_path="${build_dir}/operator.tar.gz"
source_dir="${build_dir}/source"
mkdir -p "${source_dir}"

if [[ -d "${local_source}/.git" ]]; then
  echo "Building PHPA from local fork: ${local_source}"
  tar --exclude=.git --create --file=- --directory "${local_source}" . | \
    tar --extract --file=- --directory "${source_dir}"
else
  readonly commit=${PHPA_COMMIT:-}
  readonly source_sha256=${PHPA_SOURCE_SHA256:-}
  if [[ -z "${commit}" || -z "${source_sha256}" ]]; then
    echo "Local PHPA fork not found at ${local_source}. Set PHPA_SOURCE_DIR or both PHPA_COMMIT and PHPA_SOURCE_SHA256." >&2
    exit 1
  fi
  curl --fail --silent --show-error --location \
    "${FORK_URL}/archive/${commit}.tar.gz" \
    --output "${archive_path}"
  actual_sha=$(shasum -a 256 "${archive_path}" | awk '{print $1}')
  if [[ "${actual_sha}" != "${source_sha256}" ]]; then
    echo "PHPA source checksum mismatch." >&2
    exit 1
  fi
  tar -xzf "${archive_path}" --strip-components=1 --directory "${source_dir}"
fi

docker build \
  --platform "linux/${node_arch}" \
  --build-arg TARGETOS=linux \
  --build-arg "TARGETARCH=${node_arch}" \
  --file "${source_dir}/Dockerfile" \
  --tag "${IMAGE}" \
  "${source_dir}"

constant_history='{"lookAhead":10000,"currentTime":"2026-01-01T00:01:00Z","replicaHistory":[{"time":"2026-01-01T00:00:00Z","replicas":1},{"time":"2026-01-01T00:00:10Z","replicas":1},{"time":"2026-01-01T00:00:20Z","replicas":1},{"time":"2026-01-01T00:00:30Z","replicas":1},{"time":"2026-01-01T00:00:40Z","replicas":1},{"time":"2026-01-01T00:00:50Z","replicas":1}]}'
constant_prediction=$(printf '%s' "${constant_history}" | docker run --rm --interactive \
  --platform "linux/${node_arch}" \
  --entrypoint python \
  "${IMAGE}" \
  algorithms/linear_regression/linear_regression.py)
if [[ "${constant_prediction}" != "1" ]]; then
  echo "PHPA linear regression stability check failed: expected 1, got ${constant_prediction}." >&2
  exit 1
fi

minikube image load --profile "${PROFILE}" --overwrite=true "${IMAGE}"

helm upgrade --install "${RELEASE}" "${source_dir}/helm" \
  --kube-context "${CONTEXT}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --set "image.repository=itsmekhoathekid/predictive-horizontal-pod-autoscaler" \
  --set "image.tag=${VERSION}" \
  --set "image.pullPolicy=Never" \
  --set "leaderElection.enabled=true" \
  --wait \
  --timeout 10m

kubectl --context "${CONTEXT}" rollout restart deployment/predictive-horizontal-pod-autoscaler \
  --namespace "${NAMESPACE}"
kubectl --context "${CONTEXT}" rollout status deployment/predictive-horizontal-pod-autoscaler \
  --namespace "${NAMESPACE}" \
  --timeout=300s
