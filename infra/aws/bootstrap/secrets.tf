resource "aws_secretsmanager_secret" "gemini" {
  name = "incident-agent/gemini-api-key"

  recovery_window_in_days = 7
}