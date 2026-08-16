terraform {
  required_version = ">= 1.6"
  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = "~> 1.48"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.6"
    }
  }
}

provider "hcloud" {
  token = var.hcloud_token
}

locals {
  # Hetzner attaches the private network to this interface on Ubuntu images.
  # k3s must bind flannel to it so cluster traffic stays off the public NIC.
  private_iface   = "ens10"
  network_cidr    = "10.10.0.0/16"
  subnet_cidr     = "10.10.1.0/24"
  cp_private_ip   = "10.10.1.10"
  worker_ip_start = 20
}

resource "random_password" "k3s_token" {
  length  = 48
  special = false
}

resource "hcloud_ssh_key" "admin" {
  name       = "${var.cluster_name}-admin"
  public_key = file(pathexpand(var.ssh_public_key_path))
}

# --- Networking -------------------------------------------------------------

resource "hcloud_network" "cluster" {
  name     = "${var.cluster_name}-net"
  ip_range = local.network_cidr
}

resource "hcloud_network_subnet" "cluster" {
  network_id   = hcloud_network.cluster.id
  type         = "cloud"
  network_zone = "eu-central"
  ip_range     = local.subnet_cidr
}

# --- Firewall ---------------------------------------------------------------
# Public exposure is limited to SSH and the Kubernetes API, and only from the
# operator's own address. All cluster-internal traffic uses the private network.

resource "hcloud_firewall" "cluster" {
  name = "${var.cluster_name}-fw"

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "22"
    source_ips = var.allowed_admin_ipv4
  }

  rule {
    direction  = "in"
    protocol   = "tcp"
    port       = "6443"
    source_ips = var.allowed_admin_ipv4
  }

  rule {
    direction  = "in"
    protocol   = "icmp"
    source_ips = var.allowed_admin_ipv4
  }
}

# --- Control plane ----------------------------------------------------------

resource "hcloud_server" "control_plane" {
  name         = "${var.cluster_name}-cp"
  image        = var.image
  server_type  = var.control_plane_type
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.admin.id]
  firewall_ids = [hcloud_firewall.cluster.id]

  network {
    network_id = hcloud_network.cluster.id
    ip         = local.cp_private_ip
  }

  user_data = templatefile("${path.module}/cloud-init/control-plane.yaml.tftpl", {
    k3s_version   = var.k3s_version
    k3s_token     = random_password.k3s_token.result
    private_ip    = local.cp_private_ip
    private_iface = local.private_iface
  })

  labels = {
    cluster = var.cluster_name
    role    = "control-plane"
  }

  depends_on = [hcloud_network_subnet.cluster]
}

# --- Workers ----------------------------------------------------------------

resource "hcloud_server" "worker" {
  count        = var.worker_count
  name         = "${var.cluster_name}-w${count.index + 1}"
  image        = var.image
  server_type  = var.worker_type
  location     = var.location
  ssh_keys     = [hcloud_ssh_key.admin.id]
  firewall_ids = [hcloud_firewall.cluster.id]

  network {
    network_id = hcloud_network.cluster.id
    ip         = "10.10.1.${local.worker_ip_start + count.index}"
  }

  user_data = templatefile("${path.module}/cloud-init/worker.yaml.tftpl", {
    k3s_version   = var.k3s_version
    k3s_token     = random_password.k3s_token.result
    server_ip     = local.cp_private_ip
    private_ip    = "10.10.1.${local.worker_ip_start + count.index}"
    private_iface = local.private_iface
    # Workers are labelled so scenarios can target a tier deterministically.
    node_label    = count.index < 2 ? "application" : "observability"
  })

  labels = {
    cluster = var.cluster_name
    role    = "worker"
  }

  depends_on = [hcloud_server.control_plane]
}
