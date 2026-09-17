#!/usr/bin/env bash
set -Eeuo pipefail

readonly PROFILE="predictive-hpa"
readonly CONTEXT="predictive-hpa"
readonly NAMESPACE="phpa-system"
readonly RELEASE="predictive-horizontal-pod-autoscaler-operator"
readonly VERSION="v0.13.2"
readonly COMMIT="c91d060920fb7197c74dce1323f4ba560180ed5f"
readonly SOURCE_SHA256="7e90e879ffb234a697eb0e656f3345a0d200f7997b7616fbf6738a1ac0719af3"
readonly IMAGE="jthomperoo/predictive-horizontal-pod-autoscaler:${VERSION}"
readonly CHART_URL="https://github.com/jthomperoo/predictive-horizontal-pod-autoscaler/releases/download/${VERSION}/predictive-horizontal-pod-autoscaler-${VERSION}.tgz"

project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
node_arch=$(minikube --profile "${PROFILE}" kubectl -- \
  --context "${CONTEXT}" get node -o jsonpath='{.items[0].status.nodeInfo.architecture}')

build_dir=$(mktemp -d)
trap 'rm -rf "${build_dir}"' EXIT
archive_path="${build_dir}/operator.tar.gz"
source_dir="${build_dir}/source"
mkdir -p "${source_dir}"

curl --fail --silent --show-error --location \
  "https://github.com/jthomperoo/predictive-horizontal-pod-autoscaler/archive/${COMMIT}.tar.gz" \
  --output "${archive_path}"
actual_sha=$(shasum -a 256 "${archive_path}" | awk '{print $1}')
if [[ "${actual_sha}" != "${SOURCE_SHA256}" ]]; then
  echo "PHPA source checksum mismatch." >&2
  exit 1
fi

tar -xzf "${archive_path}" --strip-components=1 --directory "${source_dir}"
cp "${project_root}/deploy/operator/Dockerfile" "${source_dir}/Dockerfile.operator"
docker build \
  --platform "linux/${node_arch}" \
  --build-arg TARGETOS=linux \
  --build-arg "TARGETARCH=${node_arch}" \
  --file "${source_dir}/Dockerfile.operator" \
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

helm upgrade --install "${RELEASE}" "${CHART_URL}" \
  --kube-context "${CONTEXT}" \
  --namespace "${NAMESPACE}" \
  --create-namespace \
  --wait \
  --timeout 10m

minikube --profile "${PROFILE}" kubectl -- \
  --context "${CONTEXT}" \
  rollout restart deployment/predictive-horizontal-pod-autoscaler \
  --namespace "${NAMESPACE}"
minikube --profile "${PROFILE}" kubectl -- \
  --context "${CONTEXT}" \
  rollout status deployment/predictive-horizontal-pod-autoscaler \
  --namespace "${NAMESPACE}" \
  --timeout=300s
