# Reference cloud environment: VPC + EKS + RDS Postgres + S3 (backups), then the
# app deployed onto EKS. Uses the well-maintained terraform-aws-modules. This is
# a documented reference — applying it provisions billable AWS resources.

data "aws_availability_zones" "available" {
  state = "available"
}

locals {
  azs = slice(data.aws_availability_zones.available.names, 0, 3)
}

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.8"

  name = "${var.name}-vpc"
  cidr = var.vpc_cidr
  azs  = local.azs

  private_subnets = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i)]
  public_subnets  = [for i in range(3) : cidrsubnet(var.vpc_cidr, 4, i + 8)]

  enable_nat_gateway = true
  single_nat_gateway = true

  # Tags required for EKS + load balancer controller discovery.
  public_subnet_tags  = { "kubernetes.io/role/elb" = "1" }
  private_subnet_tags = { "kubernetes.io/role/internal-elb" = "1" }
}

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.8"

  cluster_name    = "${var.name}-eks"
  cluster_version = var.kubernetes_version

  # Private by default; opening this up requires naming the allowed CIDRs too,
  # otherwise the upstream module exposes the API server to 0.0.0.0/0.
  cluster_endpoint_public_access       = var.cluster_endpoint_public_access
  cluster_endpoint_public_access_cidrs = var.cluster_endpoint_public_access_cidrs

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  eks_managed_node_groups = {
    default = {
      instance_types = [var.node_instance_type]
      min_size       = 1
      max_size       = 4
      desired_size   = var.node_desired_size
    }
  }
}

module "rds" {
  source  = "terraform-aws-modules/rds/aws"
  version = "~> 6.7"

  identifier = "${var.name}-db"

  engine               = "postgres"
  engine_version       = "16"
  family               = "postgres16"
  major_engine_version = "16"
  instance_class       = var.db_instance_class

  allocated_storage     = 20
  max_allocated_storage = 100

  db_name  = "apm"
  username = "apm"
  password = var.postgres_password
  port     = 5432

  multi_az               = true
  vpc_security_group_ids = [module.rds_sg.security_group_id]
  subnet_ids             = module.vpc.private_subnets
  create_db_subnet_group = true

  backup_retention_period = 7
  deletion_protection     = true
  storage_encrypted       = true
}

module "rds_sg" {
  source  = "terraform-aws-modules/security-group/aws"
  version = "~> 5.1"

  name        = "${var.name}-rds-sg"
  description = "Allow Postgres from within the VPC"
  vpc_id      = module.vpc.vpc_id

  ingress_with_cidr_blocks = [{
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    description = "Postgres from VPC"
    cidr_blocks = var.vpc_cidr
  }]
}

# Object storage for pgBackRest backups (encrypted, versioned, private).
module "backups_bucket" {
  source  = "terraform-aws-modules/s3-bucket/aws"
  version = "~> 4.1"

  bucket = "${var.name}-backups"

  force_destroy            = false
  control_object_ownership = true
  object_ownership         = "BucketOwnerPreferred"

  versioning = { enabled = true }

  server_side_encryption_configuration = {
    rule = { apply_server_side_encryption_by_default = { sse_algorithm = "AES256" } }
  }

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

module "apm" {
  source = "../../modules/apm_platform"

  namespace         = "apm"
  create_namespace  = true
  chart_path        = abspath("${path.module}/../../../../deploy/helm/apm-observability")
  image_tag         = var.image_tag
  replica_count     = 2
  values_files      = [abspath("${path.module}/../../../../deploy/helm/apm-observability/values-production.yaml")]
  django_secret_key = var.django_secret_key
  postgres_password = var.postgres_password

  # Point the app at the managed RDS instance instead of an in-cluster DB.
  extra_set = {
    "postgres.enabled"     = "false"
    "config.POSTGRES_HOST" = module.rds.db_instance_address
    "config.DB_SSLMODE"    = "require"
    "config.OTEL_ENABLED"  = "1"
  }

  depends_on = [module.eks, module.rds]
}
