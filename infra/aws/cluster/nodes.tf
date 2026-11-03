resource "aws_eks_node_group" "app" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "app"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  ami_type       = "AL2023_x86_64_STANDARD"
  capacity_type  = "ON_DEMAND"
  instance_types = ["t3.large"]

  scaling_config {
    desired_size = 2
    min_size     = 2
    max_size     = 2
  }

  labels = {
    "workload-tier" = "application"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr,
  ]
}

resource "aws_eks_node_group" "observability" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "observability"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  ami_type       = "AL2023_x86_64_STANDARD"
  capacity_type  = "ON_DEMAND"
  instance_types = ["t3.large"]

  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 1
  }

  labels = {
    "workload-tier" = "observability"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr,
  ]
}

resource "aws_eks_node_group" "system" {
  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "system"
  node_role_arn   = aws_iam_role.node.arn
  subnet_ids      = [aws_subnet.private_a.id, aws_subnet.private_b.id]

  ami_type       = "AL2023_x86_64_STANDARD"
  capacity_type  = "ON_DEMAND"
  instance_types = ["t3.medium"]

  scaling_config {
    desired_size = 1
    min_size     = 1
    max_size     = 1
  }

  labels = {
    "workload-tier" = "system"
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_worker,
    aws_iam_role_policy_attachment.node_cni,
    aws_iam_role_policy_attachment.node_ecr,
  ]
}