# Complete AWS Deployment Guide

This guide provides step-by-step instructions for deploying the entire AI-Powered RFP Response Agent system to AWS.

## 🏗️ System Architecture

The complete system consists of:

1. **AWS Infrastructure** (CloudFormation)
   - S3 buckets for storage and hosting
   - DynamoDB tables for data
   - Lambda functions for processing
   - SQS queues for messaging
   - EventBridge for orchestration
   - IAM roles and policies

2. **Java Spring Boot REST API**
   - Enterprise-grade REST API service
   - AWS SDK integration
   - Docker containerized
   - Deployable to ECS, EKS, or Elastic Beanstalk

3. **React Web UI**
   - Modern React application
   - Static hosting on S3
   - API integration for real-time data

4. **Lambda Functions**
   - SAM.gov data processing
   - AI matching and analysis
   - Report generation
   - Email notifications

## 🚀 Quick Deployment

### Option 1: Automated Full Deployment

```bash
# 1. Configure deployment settings
source deployment.env

# 2. Run simplified deployment (recommended)
./deploy-simple.sh

# 3. Or run comprehensive deployment
./deploy-system.sh
```

### Option 2: Manual Step-by-Step Deployment

#### Step 1: Deploy Infrastructure

```bash
cd deployment
powershell -File deploy-complete-stack.ps1 -StackName "ai-rfp-response-agent-dev" -BucketPrefix "l3harris-qhan" -Region "us-east-1"
```

#### Step 2: Build and Deploy Java API

```bash
cd java-api

# Build the application
mvn clean package -DskipTests

# Option A: Deploy to Elastic Beanstalk
eb init rfp-java-api --region us-east-1
eb create rfp-java-api-env --sample

# Option B: Deploy with Docker to ECS
aws ecr create-repository --repository-name rfp-java-api
docker build -t rfp-java-api .
# Push to ECR and deploy to ECS
```

#### Step 3: Deploy React UI

```bash
cd ui

# Build the application
npm install
npm run build

# Deploy to S3
powershell -File deploy.ps1 -BucketName "l3harris-qhan-rfp-ui-dev" -CreateBucket
```

#### Step 4: Configure API Gateway (Optional)

```bash
cd infrastructure
aws cloudformation deploy \
    --template-file api-gateway-stack.yaml \
    --stack-name "ai-rfp-api-gateway-dev" \
    --parameters ParameterKey=JavaApiUrl,ParameterValue=https://your-java-api-url.com
```

## 📋 Prerequisites

### Required Tools

- **AWS CLI v2** - `aws --version`
- **Docker** - `docker --version`
- **Java 17+** - `java --version`
- **Maven 3.6+** - `mvn --version`
- **Node.js 16+** - `node --version`
- **PowerShell** (optional) - `powershell --version`

### AWS Permissions

Your AWS user/role needs permissions for:

- CloudFormation (full access)
- S3 (bucket creation and management)
- Lambda (function creation and deployment)
- DynamoDB (table creation)
- IAM (role and policy creation)
- Elastic Beanstalk or ECS (for Java API)
- ECR (Docker registry)
- API Gateway
- EventBridge
- SQS

### Required Information

- **SAM.gov API Key** - Get from https://api.sam.gov/
- **Company Name** - For report templates
- **Contact Email** - For notifications
- **AWS Region** - Default: us-east-1
- **Bucket Prefix** - Unique prefix for S3 buckets

## 🔧 Configuration

### Environment Variables

Edit `deployment.env` to configure:

```bash
STACK_NAME="ai-rfp-response-agent-dev"
BUCKET_PREFIX="your-company-prefix"
REGION="us-east-1"
COMPANY_NAME="Your Company"
CONTACT_EMAIL="admin@company.com"
SAM_API_KEY="your-sam-api-key"
```

### Java API Configuration

The Java API can be configured via environment variables:

```bash
# Database (if using RDS)
SPRING_DATASOURCE_URL=jdbc:postgresql://localhost:5432/rfpdb
SPRING_DATASOURCE_USERNAME=rfpuser
SPRING_DATASOURCE_PASSWORD=password

# AWS Configuration
AWS_REGION=us-east-1
AWS_DYNAMODB_TABLE_PREFIX=ai-rfp-dev-

# Application Settings  
SERVER_PORT=8080
SPRING_PROFILES_ACTIVE=prod
```

### React UI Configuration

Update `ui/src/config.js`:

```javascript
export const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8080/api';
export const ENVIRONMENT = process.env.REACT_APP_ENVIRONMENT || 'development';
```

## 🧪 Testing Deployment

### 1. Test Infrastructure

```bash
cd deployment
powershell -File trigger-workflow.ps1 -BucketPrefix "l3harris-qhan"
```

### 2. Test Java API

```bash
# Health check
curl https://your-java-api-url.com/health

# API endpoints
curl https://your-java-api-url.com/api/opportunities
curl https://your-java-api-url.com/api/dashboard
```

### 3. Test React UI

Visit: `http://your-bucket-name.s3-website-us-east-1.amazonaws.com`

### 4. Test Complete Workflow

```bash
cd deployment
powershell -File run-complete-workflow.ps1 -OpportunitiesToProcess 5
```

## 📊 Deployment Options

### Java API Deployment Methods

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| **Elastic Beanstalk** | Easy deployment, Auto-scaling | Less control | Development/Testing |
| **ECS with Fargate** | Serverless containers, Full control | More complex | Production |
| **EKS** | Kubernetes orchestration | Complex setup | Enterprise/Scale |
| **Lambda + GraalVM** | Serverless, Pay-per-use | Cold starts, Limited runtime | Event-driven workloads |

### UI Hosting Options

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| **S3 Static Website** | Simple, Cheap | No HTTPS by default | Development |
| **CloudFront + S3** | CDN, HTTPS, Global | More complex | Production |
| **Amplify** | CI/CD integration | AWS-specific | Full-stack development |

## 🚨 Troubleshooting

### Common Issues

1. **IAM Permissions**: Ensure your AWS credentials have sufficient permissions
2. **Bucket Name Conflicts**: Use a unique bucket prefix
3. **Java Build Failures**: Check Java version (17+) and Maven configuration
4. **React Build Errors**: Verify Node.js version (16+) and npm dependencies
5. **Lambda Deployment**: Check PowerShell execution policy on Windows

### Validation Commands

```bash
# Check AWS credentials
aws sts get-caller-identity

# Verify stack deployment
aws cloudformation describe-stacks --stack-name "ai-rfp-response-agent-dev"

# Check Java API health
curl https://your-java-api-url/health

# Test Lambda functions
aws lambda invoke --function-name "your-function-name" output.json
```

## 📈 Monitoring and Maintenance

### CloudWatch Monitoring

The deployment includes:
- Lambda function logs and metrics
- Application load balancer metrics (if using ECS/EKS)
- S3 access logs
- DynamoDB performance metrics

### Cost Optimization

- Use S3 lifecycle policies for log archival
- Configure DynamoDB auto-scaling
- Set up Lambda reserved concurrency
- Monitor and optimize Elastic Beanstalk instance types

### Updates and CI/CD

Set up automated deployments:
1. GitHub Actions for continuous deployment
2. CodePipeline for AWS-native CI/CD
3. Docker image updates for containerized services

## 🎯 Next Steps

After successful deployment:

1. **Configure monitoring alerts**
2. **Set up backup strategies**
3. **Implement CI/CD pipelines**
4. **Performance testing and optimization**
5. **Security hardening and compliance**
6. **Documentation and training**

## 📞 Support

For deployment issues:
1. Check CloudFormation events in AWS Console
2. Review CloudWatch logs for Lambda functions
3. Verify IAM permissions and policies
4. Test individual components separately
5. Use AWS support if needed