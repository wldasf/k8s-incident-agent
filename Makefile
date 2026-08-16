KUBECONFIG_PATH := $(PWD)/infra/terraform/kubeconfig.yaml
export KUBECONFIG = $(KUBECONFIG_PATH)

.PHONY: up observability workload verify all down cost test kubeconfig

## Provision the Hetzner cluster (billing starts here)
up:
	@bash infra/scripts/up.sh

observability:
	@bash infra/scripts/02-observability.sh

workload:
	@bash infra/scripts/03-workload.sh

verify:
	@bash infra/scripts/04-verify.sh

## Full provision from nothing
all: up observability workload verify

## Destroy the cluster (billing stops here) - run at the end of every session
down:
	@bash infra/scripts/down.sh

## Show running resources and current spend
cost:
	@bash infra/scripts/cost.sh

kubeconfig:
	@echo "export KUBECONFIG=$(KUBECONFIG_PATH)"

test:
	@python3 -m pytest tests/ -q
