resource "aws_s3_bucket_lifecycle_configuration" "bucket_config" {
  bucket = aws_s3_bucket.results.id

  rule {
    id = "expire-old-results"

    expiration {
      days = 90
    }

    status = "Enabled"
  }
}