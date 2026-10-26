terraform {
    required_version = ">= 1.10"

    required_providers {
        aws = {
            source = "hashicorp/aws"
            version = "~> 6.0"
        }
    }

    backend "s3" {
        bucket       = "k8s-incident-agent-tfstate-28cd0372"
        key          = "cluster/terraform.tfstate"
        region       = "eu-central-1"
        use_lockfile = true
    }
}