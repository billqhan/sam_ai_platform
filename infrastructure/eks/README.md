# EKS Deployment Guide for SAM AI Java API

Complete guide for deploying the Java API to Amazon EKS with production-ready configuration.

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Detailed Setup](#detailed-setup)
- [Monitoring](#monitoring)
- [Operations](#operations)
- [Cost Optimization](#cost-optimization)
- [Troubleshooting](#troubleshooting)

## 🎯 Overview

This EKS setup provides:

- **High Availability**: Multi-AZ deployment with 2+ replicas
- **Auto-scaling**: HPA for pods, Cluster Autoscaler for nodes
- **Cost Optimization**: Spot instances for 60-70% savings
- **Security**: IRSA for AWS service access, network policies
- **Observability**: Prometheus + Grafana monitoring
- **CI/CD Ready**: Automated build and deploy scripts

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     AWS Cloud                           │
│  ┌───────────────────────────────────────────────────┐  │
│  │              VPC (10.0.0.0/16)                    │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌──────────┐  │  │
│  │  │   AZ-1      │  │   AZ-2      │  │   AZ-3   │  │  │
│  │  │             │  │             │  │          │  │  │
│  │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌──────┐ │  │  │
│  │  │ │ Public  │ │  │ │ Public  │ │  │ │Public│ │  │  │
│  │  │ │ Subnet  │ │  │ │ Subnet  │ │  │ │Subnet│ │  │  │
│  │  │ │  (ALB)  │ │  │ │  (ALB)  │ │  │ │(ALB) │ │  │  │
│  │  │ └────┬────┘ │  │ └────┬────┘ │  │ └──┬───┘ │  │  │
│  │  │      │      │  │      │      │  │    │     │  │  │
│  │  │ ┌────▼────┐ │  │ ┌────▼────┐ │  │ ┌──▼───┐ │  │  │
│  │  │ │ Private │ │  │ │ Private │ │  │ │Privat│ │  │  │
│  │  │ │ Subnet  │ │  │ │ Subnet  │ │  │ │Subnet│ │  │  │
│  │  │ │ (Nodes) │ │  │ │ (Nodes) │ │  │ │(Node)│ │  │  │
│  │  │ │         │ │  │ │         │ │  │ │      │ │  │  │
│  │  │ │  ┌──┐   │ │  │ │  ┌──┐   │ │  │ │ ┌──┐ │ │  │  │
│  │  │ │  │P │   │ │  │ │  │P │   │ │  │ │ │P │ │ │  │  │
│  │  │ │  │o │   │ │  │ │  │o │   │ │  │ │ │o │ │ │  │  │
│  │  │ │  │d │   │ │  │ │  │d │   │ │  │ │ │d │ │ │  │  │
│  │  │ │  └──┘   │ │  │ │  └──┘   │ │  │ │ └──┘ │ │  │  │
│  │  │ └─────────┘ │  │ └─────────┘ │  │ └──────┘ │  │  │
│  │  └─────────────┘  └─────────────┘  └──────────┘  │  │
│  └───────────────────────────────────────────────────┘  │
│                                                          │
│  ┌────────────┐  ┌────────────┐  ┌──────────────┐     │
│  │    ECR     │  │ DynamoDB   │  │      S3      │     │
│  │  (Images)  │  │  (Data)    │  │   (Files)    │     │
│  └────────────┘  └────────────┘  └──────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### Components:

- **EKS Cluster**: Kubernetes 1.31 control plane
- **Node Groups**: 
  - General (on-demand): 1-3 t3.medium nodes
  - Spot: 1-4 t3.medium/t3a.medium nodes (60-70% savings)
- **Networking**: 3 AZs, private/public subnets, NAT Gateway
- **ECR**: Container registry with vulnerability scanning
- **IRSA**: IAM roles for S3, DynamoDB, Lambda, SQS access
- **Monitoring**: Prometheus, Grafana, CloudWatch Container Insights

## ✅ Prerequisites

### Required Tools:

```powershell
# Check versions
terraform --version  # >= 1.5.0
aws --version        # >= 2.x
kubectl version      # >= 1.28
docker --version     # >= 20.x
helm version         # >= 3.x (optional, for monitoring)
```

### Install Missing Tools:

**Terraform:**
```powershell
# Windows (Chocolatey)
choco install terraform

# Or download from https://www.terraform.io/downloads
```

**kubectl:**
```powershell
# Windows (Chocolatey)
choco install kubernetes-cli

# Or via AWS CLI
aws eks install-kubectl-windows
```

**Helm (optional):**
```powershell
choco install kubernetes-helm
```

### AWS Configuration:

```powershell
# Configure AWS credentials
aws configure

# Verify access
aws sts get-caller-identity
```

## 🚀 Quick Start

### 1. Provision EKS Infrastructure (15-20 minutes)

```powershell
# Navigate to EKS infrastructure
cd infrastructure\eks

# Review the plan
.\provision-eks.ps1 -Action plan

# Apply (creates VPC, EKS, nodes, ECR)
.\provision-eks.ps1 -Action apply -AutoApprove

# Save outputs
terraform output > eks-outputs.txt
```

**What this creates:**
- VPC with 3 AZs (public + private subnets)
- EKS cluster (control plane)
- Managed node groups (1 on-demand + 1-4 spot)
- ECR repository for Java API
- IAM roles (IRSA) for AWS service access
- Security groups and networking

### 2. Deploy Java API (5-10 minutes)

```powershell
# Navigate to Java API
cd ..\..\java-api

# Build, push to ECR, and deploy to EKS
.\deploy-eks.ps1

# Monitor deployment
kubectl get pods -n sam-ai -w
```

**What this does:**
- Builds Maven project
- Builds Docker image
- Pushes to ECR
- Deploys to EKS with rolling update
- Creates LoadBalancer service

### 3. Verify Deployment

```powershell
# Get service URL
kubectl get svc java-api -n sam-ai

# Port forward for local testing
kubectl port-forward svc/java-api-internal 8080:8080 -n sam-ai

# Test health endpoint
curl http://localhost:8080/actuator/health
```

### 4. (Optional) Setup Monitoring

```powershell
cd ..\infrastructure\eks

# Install Prometheus + Grafana
.\setup-monitoring.ps1

# Access Grafana
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80
# Open http://localhost:3000 (admin / <password from output>)
```

## 📖 Detailed Setup

### Step 1: Review Terraform Configuration

Before provisioning, review and customize:

```hcl
# infrastructure/eks/variables.tf

variable "environment" {
  default = "dev"  # Change for prod
}

variable "node_desired_size" {
  default = 2  # Adjust based on load
}

variable "node_instance_types" {
  default = ["t3.medium", "t3a.medium"]  # Adjust for workload
}

variable "enable_spot_instances" {
  default = true  # Set false for production
}
```

### Step 2: Provision Infrastructure

```powershell
cd infrastructure\eks

# Initialize Terraform (first time only)
terraform init

# Plan (review changes)
terraform plan -var="environment=dev" -out=tfplan

# Apply
terraform apply tfplan

# Verify cluster
aws eks describe-cluster --name dev-sam-ai-eks --region us-east-1

# Configure kubectl
aws eks update-kubeconfig --name dev-sam-ai-eks --region us-east-1

# Test cluster access
kubectl get nodes
kubectl cluster-info
```

### Step 3: Configure Kubernetes Resources

Update manifests with your values:

```yaml
# java-api/k8s/deployment.yaml

# Update service account IAM role ARN (from Terraform output)
metadata:
  annotations:
    eks.amazonaws.com/role-arn: <java_api_service_account_role_arn>

# Update ECR image URL (from Terraform output)
spec:
  containers:
  - image: <ecr_repository_url>:dev-latest
```

### Step 4: Deploy Application

**Manual deployment:**

```powershell
cd java-api

# Build application
.\build.sh

# Build Docker image
docker build -t sam-ai-java-api:dev-latest .

# Login to ECR
$ACCOUNT_ID = (aws sts get-caller-identity --query Account --output text)
$ECR_URL = "$ACCOUNT_ID.dkr.ecr.us-east-1.amazonaws.com/sam-ai-java-api"
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_URL

# Tag and push
docker tag sam-ai-java-api:dev-latest "${ECR_URL}:dev-latest"
docker push "${ECR_URL}:dev-latest"

# Deploy to Kubernetes
kubectl create namespace sam-ai
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/monitoring.yaml
```

**Automated deployment:**

```powershell
# All-in-one script
.\deploy-eks.ps1

# Skip build (if already built)
.\deploy-eks.ps1 -SkipBuild

# Skip deployment (build and push only)
.\deploy-eks.ps1 -SkipDeploy
```

### Step 5: Verify Deployment

```powershell
# Check pods
kubectl get pods -n sam-ai

# Expected output:
# NAME                        READY   STATUS    RESTARTS   AGE
# java-api-xxxxxxxxx-xxxxx    1/1     Running   0          2m
# java-api-xxxxxxxxx-xxxxx    1/1     Running   0          2m

# Check services
kubectl get svc -n sam-ai

# View logs
kubectl logs -f deployment/java-api -n sam-ai

# Check HPA status
kubectl get hpa -n sam-ai

# Describe pod for issues
kubectl describe pod <pod-name> -n sam-ai
```

## 📊 Monitoring

### Install Monitoring Stack

```powershell
cd infrastructure\eks
.\setup-monitoring.ps1
```

This installs:
- **Prometheus**: Metrics collection and alerting
- **Grafana**: Visualization dashboards
- **AlertManager**: Alert routing and notification

### Access Grafana

```powershell
# Port forward
kubectl port-forward -n monitoring svc/monitoring-grafana 3000:80

# Get admin password
kubectl get secret monitoring-grafana -n monitoring -o jsonpath="{.data.admin-password}" | ForEach-Object { [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($_)) }

# Open browser
Start-Process http://localhost:3000
```

### Pre-configured Dashboards

- **Spring Boot Dashboard** (ID: 12900)
- **JVM Dashboard** (ID: 4701)
- **Kubernetes Cluster** (ID: 15760)

### Key Metrics to Monitor

```promql
# Request rate
rate(http_server_requests_seconds_count[5m])

# Error rate
rate(http_server_requests_seconds_count{status=~"5.."}[5m])

# Latency (95th percentile)
histogram_quantile(0.95, rate(http_server_requests_seconds_bucket[5m]))

# JVM memory usage
jvm_memory_used_bytes{area="heap"} / jvm_memory_max_bytes{area="heap"}

# Pod CPU usage
container_cpu_usage_seconds_total{namespace="sam-ai", pod=~"java-api-.*"}
```

### CloudWatch Container Insights

```powershell
# Enable cluster logging
aws eks update-cluster-config `
  --name dev-sam-ai-eks `
  --logging '{"clusterLogging":[{"types":["api","audit","authenticator","controllerManager","scheduler"],"enabled":true}]}'
```

## 🔧 Operations

### Scaling

**Manual scaling:**

```powershell
# Scale deployment
kubectl scale deployment/java-api --replicas=5 -n sam-ai

# Scale node group (via Terraform)
terraform apply -var="node_desired_size=5"
```

**Auto-scaling:**

```powershell
# HPA is already configured (2-10 replicas)
kubectl get hpa -n sam-ai

# View HPA events
kubectl describe hpa java-api-hpa -n sam-ai

# Cluster Autoscaler watches for pending pods
kubectl logs -f deployment/cluster-autoscaler -n kube-system
```

### Updates and Rollouts

**Update image:**

```powershell
# Build and push new image
.\deploy-eks.ps1

# Or set specific image
kubectl set image deployment/java-api java-api=<new-image> -n sam-ai

# Monitor rollout
kubectl rollout status deployment/java-api -n sam-ai

# View rollout history
kubectl rollout history deployment/java-api -n sam-ai
```

**Rollback:**

```powershell
# Rollback to previous version
kubectl rollout undo deployment/java-api -n sam-ai

# Rollback to specific revision
kubectl rollout undo deployment/java-api --to-revision=2 -n sam-ai
```

### Configuration Updates

**Update ConfigMap:**

```powershell
# Edit ConfigMap
kubectl edit configmap java-api-config -n sam-ai

# Restart pods to pick up changes
kubectl rollout restart deployment/java-api -n sam-ai
```

**Update Secrets:**

```powershell
# Update secret
kubectl edit secret java-api-secrets -n sam-ai

# Restart deployment
kubectl rollout restart deployment/java-api -n sam-ai
```

### Logs

```powershell
# Stream logs
kubectl logs -f deployment/java-api -n sam-ai

# Last 100 lines
kubectl logs --tail=100 deployment/java-api -n sam-ai

# Specific pod
kubectl logs <pod-name> -n sam-ai

# Previous crashed pod
kubectl logs <pod-name> -n sam-ai --previous
```

### Shell Access

```powershell
# Execute shell in pod
kubectl exec -it <pod-name> -n sam-ai -- /bin/sh

# Run command
kubectl exec <pod-name> -n sam-ai -- curl localhost:8080/actuator/health
```

## 💰 Cost Optimization

### Current Setup Costs (Estimated)

**Development Environment:**
- EKS Control Plane: $73/month
- 2x t3.medium nodes (spot): ~$20/month
- NAT Gateway: $33/month
- Load Balancer (NLB): $17/month
- **Total: ~$143/month**

**Production Environment:**
- EKS Control Plane: $73/month
- 3x t3.large nodes (on-demand): ~$150/month
- NAT Gateway (3 AZs): $99/month
- Load Balancer (ALB): $23/month
- **Total: ~$345/month**

### Cost Reduction Strategies

1. **Use Spot Instances** (enabled by default)
   - 60-70% savings on compute
   - Already configured with spot node group

2. **Right-size Nodes**
   ```hcl
   # For low traffic, use smaller instances
   node_instance_types = ["t3.small", "t3a.small"]
   
   # For CPU-intensive workloads
   node_instance_types = ["c6i.large", "c6a.large"]
   ```

3. **Single NAT Gateway** (dev only)
   ```hcl
   single_nat_gateway = true  # Already set for dev
   ```

4. **Savings Plans**
   - 1-year: 31% discount
   - 3-year: 48% discount
   - Apply to on-demand nodes

5. **Schedule Node Scaling**
   ```bash
   # Scale down at night (cron job)
   0 22 * * * kubectl scale deployment/java-api --replicas=1 -n sam-ai
   0 6 * * * kubectl scale deployment/java-api --replicas=2 -n sam-ai
   ```

6. **Use Fargate (serverless)**
   - No node management
   - Pay per pod
   - Good for bursty workloads

## 🔍 Troubleshooting

### Pod Not Starting

```powershell
# Check pod status
kubectl describe pod <pod-name> -n sam-ai

# Common issues:
# 1. Image pull error (ECR auth)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ecr-url>

# 2. Insufficient resources
kubectl get nodes
kubectl top nodes

# 3. Failed health checks
kubectl logs <pod-name> -n sam-ai
```

### Service Not Accessible

```powershell
# Check service
kubectl get svc java-api -n sam-ai

# Check endpoints
kubectl get endpoints java-api -n sam-ai

# Check security groups (if LoadBalancer)
aws ec2 describe-security-groups --filters Name=tag:kubernetes.io/cluster/dev-sam-ai-eks,Values=owned

# Test internal connectivity
kubectl run test --rm -it --image=busybox --restart=Never -- wget -O- java-api-internal.sam-ai.svc.cluster.local:8080/actuator/health
```

### High Memory Usage

```powershell
# Check memory limits
kubectl describe pod <pod-name> -n sam-ai

# Update JVM settings in deployment.yaml
env:
- name: JAVA_OPTS
  value: "-XX:MaxRAMPercentage=75.0 -XX:+UseG1GC"

# Increase resource limits
resources:
  limits:
    memory: "4Gi"
```

### Cluster Access Issues

```powershell
# Update kubeconfig
aws eks update-kubeconfig --name dev-sam-ai-eks --region us-east-1

# Verify IAM permissions
aws eks describe-cluster --name dev-sam-ai-eks

# Check aws-auth ConfigMap
kubectl get configmap aws-auth -n kube-system -o yaml
```

### Node Issues

```powershell
# Check node status
kubectl get nodes
kubectl describe node <node-name>

# Check node logs (via SSM)
aws ssm start-session --target <instance-id>

# Drain node for maintenance
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data

# Uncordon node
kubectl uncordon <node-name>
```

## 📚 Additional Resources

- [EKS Best Practices](https://aws.github.io/aws-eks-best-practices/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Spring Boot Actuator](https://docs.spring.io/spring-boot/docs/current/reference/html/actuator.html)
- [Prometheus Operator](https://prometheus-operator.dev/)
- [AWS Load Balancer Controller](https://kubernetes-sigs.github.io/aws-load-balancer-controller/)

## 🆘 Support

For issues specific to this deployment:

1. Check logs: `kubectl logs -f deployment/java-api -n sam-ai`
2. Check events: `kubectl get events -n sam-ai --sort-by='.lastTimestamp'`
3. Review Grafana dashboards for metrics
4. Contact: bill.han@l3harris.com
