KUBECONFIG_PATH := $(PWD)/infra/terraform/kubeconfig.yaml

.PHONY: up observability workload verify all down cost kubeconfig aws-down aws-up aws-check

## Provision the Hetzner cluster (billing starts here)
up:
	@bash infra/scripts/up.sh

observability:
	@KUBECONFIG=$(KUBECONFIG_PATH) bash infra/scripts/02-observability.sh

workload:
	@KUBECONFIG=$(KUBECONFIG_PATH) bash infra/scripts/03-workload.sh

verify:
	@KUBECONFIG=$(KUBECONFIG_PATH) bash infra/scripts/04-verify.sh

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


fixip:
	@bash infra/scripts/allow-my-ip.sh

## Destroy the AWS cluster (billing stops here)
aws-down:
	terraform -chdir=infra/aws/cluster destroy
	terraform -chdir=infra/aws/cluster state list
	$(MAKE) aws-check

## Provision the AWS cluster (billing starts here)
aws-up:
	terraform -chdir=infra/aws/cluster init
	terraform -chdir=infra/aws/cluster apply
	aws eks update-kubeconfig --region eu-central-1 --name incident-agent
	@bash infra/aws/scripts/01-cluster-ready.sh
	@bash infra/aws/scripts/02-observability.sh
	@bash infra/aws/scripts/03-workload.sh
	kubectl apply -f infra/aws/k8s/harness-rbac.yaml
	@bash infra/aws/scripts/04-verify.sh

## Check that EC2, EKS, and ELB are destroyed
aws-check:
	@echo "NAT Gateways:"
	@aws ec2 describe-nat-gateways --filter Name=state,Values=pending,available --query 'NatGateways[].NatGatewayId'
	@echo "Elastic IPs:"
	@aws ec2 describe-addresses --query 'Addresses[].PublicIp'
	@echo "EKS Clusters:"
	@aws eks list-clusters --query clusters
	@echo "EC2 Instances:"
	@aws ec2 describe-instances --filters Name=instance-state-name,Values=pending,running --query 'Reservations[].Instances[].InstanceId'
	@echo "Elastic Loadbalancers:"
	@aws elb describe-load-balancers --query 'LoadBalancerDescriptions[].LoadBalancerName'
