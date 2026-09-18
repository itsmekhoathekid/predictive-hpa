PROFILE := predictive-hpa
NAMESPACE := predictive-hpa-demo
KUBE := kubectl --context $(PROFILE)

.PHONY: install train format lint typecheck test quality cluster operator deploy setup status logs load-ui demo mode-linear mode-datapoint mode-minibatch restart-test destroy

install:
	uv sync --all-groups

train:
	uv run --group training python -m training.train

format:
	uv run --group test ruff format .
	uv run --group test ruff check --fix .

lint:
	uv run --group test ruff format --check .
	uv run --group test ruff check .

typecheck:
	uv run --group training --group test mypy

test:
	uv run --group training --group test pytest

quality: lint typecheck test

cluster:
	./scripts/cluster-up.sh

operator:
	./scripts/install-operator.sh

deploy:
	docker build --tag house-price-api:local .
	minikube image load --profile $(PROFILE) --overwrite=true house-price-api:local
	$(KUBE) apply --filename deploy/k8s/namespace.yaml
	$(KUBE) apply --filename deploy/k8s/application.yaml
	$(KUBE) rollout status deployment/house-price-api --namespace $(NAMESPACE) --timeout=180s
	$(KUBE) apply --filename deploy/k8s/phpa.yaml

setup: cluster operator deploy

status:
	$(KUBE) get deployments,pods,services,phpa --namespace $(NAMESPACE)
	@$(KUBE) top pods --namespace $(NAMESPACE) || \
		echo "Pod metrics are not available yet; wait for the first Metrics Server sample."

logs:
	$(KUBE) logs --namespace phpa-system --selector name=predictive-horizontal-pod-autoscaler --follow

load-ui:
	uv run --group load locust --locustfile loadtest/locustfile.py --host http://127.0.0.1:8000

demo:
	./scripts/demo-autoscaling.sh

mode-linear:
	$(KUBE) apply --filename deploy/k8s/phpa-linear.yaml

mode-datapoint:
	$(KUBE) apply --filename deploy/k8s/phpa.yaml

mode-minibatch:
	$(KUBE) apply --filename deploy/k8s/phpa-minibatch.yaml

restart-test:
	./scripts/test-operator-restart.sh

destroy:
	minikube delete --profile $(PROFILE)
