# Remote state in S3 with DynamoDB locking.
#
# Bootstrap the bucket + table once (out-of-band), then `terraform init`.
# Left commented so `terraform init -backend=false` works in CI for validation.
#
# terraform {
#   backend "s3" {
#     bucket         = "apm-observability-tfstate"
#     key            = "aws/terraform.tfstate"
#     region         = "eu-west-1"
#     dynamodb_table = "apm-observability-tflock"
#     encrypt        = true
#   }
# }
