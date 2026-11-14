resource "aws_eks_addon" "pod_identity" {
  cluster_name = aws_eks_cluster.main.name
  addon_name   = "eks-pod-identity-agent"
}

resource "aws_iam_role" "harness" {
  name = "incident-agent-harness"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "pods.eks.amazonaws.com" }
      Action    = ["sts:AssumeRole", "sts:TagSession"]
    }]
  })
}

data "aws_secretsmanager_secret" "gemini" {
  name = "incident-agent/gemini-api-key"
}

locals {
  results_bucket = "k8s-incident-agent-results-c897c1b9"
}

resource "aws_iam_role_policy" "harness" {
  name = "harness-access"
  role = aws_iam_role.harness.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = data.aws_secretsmanager_secret.gemini.arn
      },
      {
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "arn:aws:s3:::${local.results_bucket}/runs/*"
      },
    ]
  })
}

resource "aws_eks_pod_identity_association" "harness" {
  cluster_name    = aws_eks_cluster.main.name
  namespace       = "harness"
  service_account = "harness"
  role_arn        = aws_iam_role.harness.arn
}