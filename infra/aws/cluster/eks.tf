resource "aws_eks_cluster" "main" {
  name     = "incident-agent"
  version  = "1.37"
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    endpoint_private_access = true
    endpoint_public_access  = true
    public_access_cidrs     = local.admin_cidrs
  }

  access_config {
    authentication_mode                         = "API"
    bootstrap_cluster_creator_admin_permissions = true
  }

  upgrade_policy {
    support_type = "STANDARD"
  }
  depends_on = [aws_iam_role_policy_attachment.cluster]
}