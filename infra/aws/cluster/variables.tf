data "http" "my_ip" {
  url = "https://checkip.amazonaws.com"
}

locals {
  admin_cidrs = ["${chomp(data.http.my_ip.response_body)}/32"]
}