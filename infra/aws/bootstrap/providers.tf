provider "aws" {
  region = "eu-central-1"

  default_tags {
    tags = {
      project    = "k8s-incident-agent"
      managed-by = "terraform"
    }
  }
}