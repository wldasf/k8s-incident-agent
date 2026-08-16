output "control_plane_ip" {
  description = "Public IPv4 of the control plane."
  value       = hcloud_server.control_plane.ipv4_address
}

output "worker_ips" {
  description = "Public IPv4 addresses of the workers."
  value       = hcloud_server.worker[*].ipv4_address
}

output "kubeconfig_command" {
  description = "Fetch the kubeconfig and rewrite it for external access."
  value       = <<-EOT
    ssh root@${hcloud_server.control_plane.ipv4_address} 'cat /etc/rancher/k3s/k3s.yaml' \
      | sed 's/127.0.0.1/${hcloud_server.control_plane.ipv4_address}/' > kubeconfig.yaml
    export KUBECONFIG=$PWD/kubeconfig.yaml
  EOT
}

output "estimated_monthly_eur" {
  description = "Rough monthly cap if left running continuously. Verify current prices."
  value       = "~EUR 37/month at 24/7; hourly billing means real cost is far lower"
}
