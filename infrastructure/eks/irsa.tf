# IRSA for Java API to access AWS services
module "java_api_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name = "${var.environment}-sam-ai-java-api"
  
  role_policy_arns = {
    s3_access      = aws_iam_policy.java_api_s3.arn
    dynamodb       = aws_iam_policy.java_api_dynamodb.arn
    lambda_invoke  = aws_iam_policy.java_api_lambda.arn
    sqs            = aws_iam_policy.java_api_sqs.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["default:sam-ai-java-api"]
    }
  }

  tags = local.tags
}

# S3 access policy
resource "aws_iam_policy" "java_api_s3" {
  name        = "${var.environment}-sam-ai-java-api-s3"
  description = "S3 access for Java API"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.environment}-sam-*/*",
          "arn:aws:s3:::${var.environment}-sam-*"
        ]
      }
    ]
  })

  tags = local.tags
}

# DynamoDB access policy
resource "aws_iam_policy" "java_api_dynamodb" {
  name        = "${var.environment}-sam-ai-java-api-dynamodb"
  description = "DynamoDB access for Java API"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
          "dynamodb:BatchGetItem",
          "dynamodb:BatchWriteItem"
        ]
        Resource = "arn:aws:dynamodb:${var.aws_region}:${local.account_id}:table/${var.environment}-sam-*"
      }
    ]
  })

  tags = local.tags
}

# Lambda invoke policy
resource "aws_iam_policy" "java_api_lambda" {
  name        = "${var.environment}-sam-ai-java-api-lambda"
  description = "Lambda invocation for Java API"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "lambda:InvokeFunction",
          "lambda:InvokeAsync"
        ]
        Resource = "arn:aws:lambda:${var.aws_region}:${local.account_id}:function:${var.environment}-sam-*"
      }
    ]
  })

  tags = local.tags
}

# SQS access policy
resource "aws_iam_policy" "java_api_sqs" {
  name        = "${var.environment}-sam-ai-java-api-sqs"
  description = "SQS access for Java API"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "sqs:SendMessage",
          "sqs:ReceiveMessage",
          "sqs:DeleteMessage",
          "sqs:GetQueueAttributes",
          "sqs:GetQueueUrl"
        ]
        Resource = "arn:aws:sqs:${var.aws_region}:${local.account_id}:${var.environment}-sqs-sam-*"
      }
    ]
  })

  tags = local.tags
}

# IRSA for AWS Load Balancer Controller
module "aws_load_balancer_controller_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                              = "${var.environment}-aws-load-balancer-controller"
  attach_load_balancer_controller_policy = true

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }

  tags = local.tags
}

# IRSA for Cluster Autoscaler
module "cluster_autoscaler_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"

  role_name                        = "${var.environment}-cluster-autoscaler"
  attach_cluster_autoscaler_policy = true
  cluster_autoscaler_cluster_names = [local.cluster_name]

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:cluster-autoscaler"]
    }
  }

  tags = local.tags
}
