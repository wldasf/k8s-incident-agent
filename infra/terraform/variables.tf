variable "hcloud_token" {
  description = "Hetzner Cloud API token (Project > Security > API Tokens, Read & Write)."
  type        = string
  sensitive   = true
}

variable "cluster_name" {
  type    = string
  default = "incident-agent"
}

variable "location" {
  description = "Hetzner location. fsn1/nbg1 (Germany), hel1 (Finland) are the cheapest."
  type        = string
  default     = "fsn1"
}

# NOTE ON SERVER TYPES
# Hetzner repriced heavily in 2026: the CPX and CCX (dedicated/AMD) lines rose
# by roughly 144-176%, while the cost-optimised CX line rose only ~33-38%.
# Use CX. Do not use CPX or CCX for this project.
#
# The ARM-based CAX line is marginally cheaper still, but the Online Boutique
# images are not guaranteed multi-architecture. On a deadline-constrained
# project the ~EUR 0.50/month saving is not worth the risk of discovering an
# image incompatibility mid-experiment. Verify arm64 support before switching.

variable "control_plane_type" {
  description = "Control-plane server type. CX23 = 2 vCPU / 4 GB."
  type        = string
  default     = "cx23"
}

variable "worker_type" {
  description = "Worker server type. CX33 = 4 vCPU / 8 GB."
  type        = string
  default     = "cx33"
}

variable "worker_count" {
  description = "Number of workers. Three is the minimum for meaningful drain and partition scenarios."
  type        = number
  default     = 3
}

variable "image" {
  type    = string
  default = "ubuntu-24.04"
}

variable "ssh_public_key_path" {
  type    = string
  default = "~/.ssh/id_ed25519.pub"
}

variable "allowed_admin_ipv4" {
  description = <<-EOT
    CIDR blocks permitted to reach SSH and the Kubernetes API.
    Set this to your own address (e.g. "203.0.113.7/32"); find it with
    `curl -4 ifconfig.me`. Leaving this as 0.0.0.0/0 exposes the API server
    to the internet and must not be used.
  EOT
  type        = list(string)
  default     = []
}

variable "k3s_version" {
  description = "Pinned k3s version. Pinning is required for reproducibility."
  type        = string
  default     = "v1.31.4+k3s1"
}
