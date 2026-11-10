output "state_bucket_name" {
  value = aws_s3_bucket.tfstate.bucket
}

output "ecr_repository_url" {
  value = aws_ecr_repository.harness.repository_url
}

output "results_bucket_name" {
  value = aws_s3_bucket.results.bucket
}