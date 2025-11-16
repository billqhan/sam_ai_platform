# ECS Cluster
resource "aws_ecs_cluster" "this" {
  name = "${var.environment}-sam-ai-ecs"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }
}

# CloudWatch Logs
resource "aws_cloudwatch_log_group" "java_api" {
  name              = "/ecs/${var.environment}/java-api"
  retention_in_days = 14
}

# Security groups
resource "aws_security_group" "alb" {
  name        = "${var.environment}-java-api-alb-sg"
  description = "ALB security group"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "tasks" {
  name        = "${var.environment}-java-api-tasks-sg"
  description = "Tasks security group"
  vpc_id      = module.vpc.vpc_id

  ingress {
    from_port       = var.container_port
    to_port         = var.container_port
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# ALB
resource "aws_lb" "this" {
  name               = "${var.environment}-java-api-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = module.vpc.public_subnets
}

resource "aws_lb_target_group" "java_api" {
  name        = "${var.environment}-java-api-tg"
  port        = var.container_port
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = "/actuator/health"
    port                = "traffic-port"
    healthy_threshold   = 2
    unhealthy_threshold = 2
    interval            = 15
    timeout             = 5
    matcher             = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.this.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.java_api.arn
  }
}

# IAM Roles
resource "aws_iam_role" "task_execution" {
  name               = "${var.environment}-java-api-exec"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}

data "aws_iam_policy_document" "ecs_task_assume" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role_policy_attachment" "execution" {
  role       = aws_iam_role.task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task role for app AWS access
resource "aws_iam_role" "task_role" {
  name               = "${var.environment}-java-api-task"
  assume_role_policy = data.aws_iam_policy_document.ecs_task_assume.json
}

# App access policies (adjust as needed)
resource "aws_iam_policy" "app_access" {
  name        = "${var.environment}-java-api-access"
  description = "App access to S3, DynamoDB, Lambda, SQS"

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject","s3:PutObject","s3:ListBucket"], Resource = ["arn:aws:s3:::${var.environment}-sam-*","arn:aws:s3:::${var.environment}-sam-*/*"] },
      { Effect = "Allow", Action = ["dynamodb:GetItem","dynamodb:PutItem","dynamodb:UpdateItem","dynamodb:Query","dynamodb:Scan"], Resource = "arn:aws:dynamodb:${var.aws_region}:${data.aws_caller_identity.current.account_id}:table/${var.environment}-sam-*" },
      { Effect = "Allow", Action = ["lambda:InvokeFunction"], Resource = "arn:aws:lambda:${var.aws_region}:${data.aws_caller_identity.current.account_id}:function:${var.environment}-sam-*" },
      { Effect = "Allow", Action = ["sqs:SendMessage","sqs:ReceiveMessage","sqs:DeleteMessage","sqs:GetQueueAttributes","sqs:GetQueueUrl"], Resource = "arn:aws:sqs:${var.aws_region}:${data.aws_caller_identity.current.account_id}:${var.environment}-sqs-sam-*" }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "task_app" {
  role       = aws_iam_role.task_role.name
  policy_arn = aws_iam_policy.app_access.arn
}

# ECR repo reference (created by EKS stack)
data "aws_ecr_repository" "java_api" {
  name = "sam-ai-java-api"
}

# Task Definition
resource "aws_ecs_task_definition" "java_api" {
  family                   = "${var.environment}-java-api"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = tostring(var.cpu)
  memory                   = tostring(var.memory)
  execution_role_arn       = aws_iam_role.task_execution.arn
  task_role_arn            = aws_iam_role.task_role.arn

  container_definitions = jsonencode([
    {
      name      = "java-api",
      image     = "${data.aws_ecr_repository.java_api.repository_url}:dev-latest",
      essential = true,
      portMappings = [{
        containerPort = var.container_port,
        hostPort      = var.container_port,
        protocol      = "tcp"
      }],
      environment = [
        { name = "SPRING_PROFILES_ACTIVE", value = "aws,ecs" },
        { name = "ENVIRONMENT", value = var.environment },
        { name = "AWS_REGION",  value = var.aws_region }
      ],
      logConfiguration = {
        logDriver = "awslogs",
        options = {
          awslogs-group         = aws_cloudwatch_log_group.java_api.name,
          awslogs-region        = var.aws_region,
          awslogs-stream-prefix = "java-api"
        }
      },
      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8081/actuator/health || exit 1"],
        interval    = 30,
        timeout     = 5,
        retries     = 3,
        startPeriod = 60
      }
    }
  ])
}

# ECS Service
resource "aws_ecs_service" "java_api" {
  name            = "${var.environment}-java-api"
  cluster         = aws_ecs_cluster.this.id
  task_definition = aws_ecs_task_definition.java_api.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  network_configuration {
    subnets         = module.vpc.private_subnets
    security_groups = [aws_security_group.tasks.id]
    assign_public_ip = false
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.java_api.arn
    container_name   = "java-api"
    container_port   = var.container_port
  }

  lifecycle {
    ignore_changes = [task_definition] # allow force-new-deployment on same task def
  }

  depends_on = [aws_lb_listener.http]
}
