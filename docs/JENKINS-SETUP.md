# Jenkins CI/CD Setup Guide

## Quick Start

### 1. Run Jenkins Locally (Docker)

```bash
# Start Jenkins
docker run -d \
  --name jenkins \
  -p 8080:8080 -p 50000:50000 \
  -v jenkins_home:/var/jenkins_home \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -u root \
  jenkins/jenkins:lts

# Get initial password
docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword

# Access Jenkins
open http://localhost:8080
```

### 2. Initial Configuration

1. **Unlock Jenkins**: Paste the initial admin password
2. **Install Plugins**: Select "Install suggested plugins"
3. **Create Admin User**
4. **Set Jenkins URL**: http://localhost:8080

### 3. Install Required Plugins

Go to **Manage Jenkins → Plugins → Available**

**Essential Plugins**:
- ✅ Pipeline
- ✅ Docker Pipeline
- ✅ AWS Steps
- ✅ Amazon ECR
- ✅ CloudBees AWS Credentials
- ✅ NodeJS Plugin
- ✅ Git
- ✅ GitHub/Bitbucket Integration

**Install command** (from Jenkins script console):
```groovy
def plugins = [
    'pipeline-model-definition',
    'docker-workflow',
    'pipeline-aws',
    'amazon-ecr',
    'aws-credentials',
    'nodejs',
    'git',
    'github',
    'workflow-aggregator'
]

def pluginManager = Jenkins.instance.pluginManager
def updateCenter = Jenkins.instance.updateCenter

plugins.each {
    if (!pluginManager.getPlugin(it)) {
        def plugin = updateCenter.getPlugin(it)
        plugin.deploy(true)
    }
}
```

### 4. Configure AWS Credentials

**Manage Jenkins → Credentials → System → Global credentials**

Add new credentials:
- **Kind**: AWS Credentials
- **ID**: `aws-credentials`
- **Access Key ID**: Your AWS access key
- **Secret Access Key**: Your AWS secret key
- **Description**: AWS Deployment Credentials

### 5. Configure Tools

**Manage Jenkins → Tools**

**NodeJS**:
- Name: `NodeJS-18`
- Install automatically: Yes
- Version: NodeJS 18.x

**Docker**:
- Name: `docker`
- Install automatically: Yes

**Maven** (if not using Docker):
- Name: `Maven-3.9`
- Install automatically: Yes
- Version: 3.9.x

## Create Jenkins Jobs

### Option 1: Pipeline from SCM (Recommended)

1. **New Item → Pipeline**
2. **Name**: `ai-platform-complete`
3. **Pipeline**:
   - Definition: Pipeline script from SCM
   - SCM: Git
   - Repository URL: `https://github.com/billqhan/sam_ai_platform.git`
   - Branch: `*/main`
   - Script Path: `Jenkinsfile`
4. **Save**

### Option 2: Multibranch Pipeline

1. **New Item → Multibranch Pipeline**
2. **Name**: `ai-platform`
3. **Branch Sources**: Add Git/GitHub
4. **Repository URL**: Your repo URL
5. **Discover branches**: All branches
6. **Build Configuration**: by Jenkinsfile
7. **Save**

This will automatically create jobs for each branch!

### Option 3: Multiple Individual Jobs

Create separate jobs for each component:

```
├── ai-platform-ui           (uses Jenkinsfile.ui)
├── ai-platform-lambda       (uses Jenkinsfile.lambda)
└── ai-platform-java-api     (uses Jenkinsfile.java)
```

## Jenkins Job Configuration

### UI Deployment Job

```groovy
// Jenkinsfile.ui location
pipeline {
    agent { docker { image 'node:18' } }
    // ... see Jenkinsfile.ui
}
```

**Trigger**: Poll SCM `H/5 * * * *` (every 5 minutes)

### Lambda Deployment Job

```groovy
// Jenkinsfile.lambda location
pipeline {
    agent { docker { image 'python:3.11' } }
    // ... see Jenkinsfile.lambda
}
```

**Parameters**:
- Choice: Select specific Lambda or "all"

### Java API Deployment Job

```groovy
// Jenkinsfile.java location
pipeline {
    agent any
    // ... see Jenkinsfile.java
}
```

**Post-build**: Archive artifacts `*.jar`

## Testing Individual Pipelines

### Test UI Pipeline

```bash
# Trigger manually via Jenkins UI
# Or via CLI
curl -X POST http://localhost:8080/job/ai-platform-ui/build \
  --user admin:your-token
```

### Test Lambda Pipeline

```bash
# With parameter
curl -X POST 'http://localhost:8080/job/ai-platform-lambda/buildWithParameters?LAMBDA_FUNCTION=sam-produce-web-reports' \
  --user admin:your-token
```

### Test Java API Pipeline

```bash
# Full build and deploy
curl -X POST http://localhost:8080/job/ai-platform-java-api/build \
  --user admin:your-token
```

## Jenkins on AWS EC2 (Production Setup)

### Launch EC2 Instance

```bash
# Launch t3.medium (minimum)
aws ec2 run-instances \
  --image-id ami-0c55b159cbfafe1f0 \
  --instance-type t3.medium \
  --key-name your-key \
  --security-groups jenkins-sg \
  --tag-specifications 'ResourceType=instance,Tags=[{Key=Name,Value=jenkins-server}]'

# Security group rules
# Allow: 8080 (Jenkins UI), 22 (SSH), 50000 (agents)
```

### Install Jenkins on EC2

```bash
# Connect to instance
ssh -i your-key.pem ec2-user@<instance-ip>

# Install Java
sudo amazon-linux-extras install java-openjdk17 -y

# Install Jenkins
sudo wget -O /etc/yum.repos.d/jenkins.repo \
    https://pkg.jenkins.io/redhat-stable/jenkins.repo
sudo rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io-2023.key
sudo yum install jenkins -y

# Install Docker
sudo yum install docker -y
sudo usermod -aG docker jenkins
sudo systemctl start docker
sudo systemctl enable docker

# Start Jenkins
sudo systemctl start jenkins
sudo systemctl enable jenkins

# Get initial password
sudo cat /var/lib/jenkins/secrets/initialAdminPassword
```

### Configure IAM Role (Better than credentials)

1. Create IAM role with policies:
   - `AmazonEC2ContainerRegistryFullAccess`
   - `AmazonECS_FullAccess`
   - `AmazonS3FullAccess`
   - `AWSLambda_FullAccess`
   - `CloudFrontFullAccess`

2. Attach role to EC2 instance

3. In Jenkins, use AWS credentials plugin without keys

## Monitoring & Debugging

### View Build Logs

```bash
# SSH to Jenkins container
docker exec -it jenkins bash

# View logs
tail -f /var/jenkins_home/jobs/*/builds/*/log

# Check disk space
df -h /var/jenkins_home
```

### Common Issues

**Issue 1: Docker permission denied**
```bash
# Add Jenkins user to docker group
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
```

**Issue 2: AWS credentials not found**
```bash
# Check AWS CLI works
aws sts get-caller-identity

# Verify credentials in Jenkins
# Manage Jenkins → Credentials → Test connection
```

**Issue 3: Build fails with "No space left on device"**
```bash
# Clean old builds
docker system prune -a -f

# Increase Docker disk space
# Adjust docker daemon settings
```

## Pipeline Best Practices

### 1. Use Declarative Pipeline (not Scripted)
```groovy
pipeline {
    agent any
    stages { ... }  // Better than node { ... }
}
```

### 2. Use Docker Agents
```groovy
agent {
    docker {
        image 'node:18'
        args '-v $HOME/.npm:/root/.npm'  // Cache dependencies
    }
}
```

### 3. Parallel Stages
```groovy
stage('Parallel Deploy') {
    parallel {
        stage('UI') { ... }
        stage('Lambda') { ... }
    }
}
```

### 4. Stash/Unstash for Artifacts
```groovy
stage('Build') {
    steps {
        sh 'npm run build'
        stash name: 'dist', includes: 'dist/**'
    }
}
stage('Deploy') {
    steps {
        unstash 'dist'
        sh 'aws s3 sync dist/ s3://bucket/'
    }
}
```

### 5. Manual Approval Gates
```groovy
stage('Deploy to Prod') {
    steps {
        input message: 'Deploy to production?', ok: 'Deploy'
        // deployment steps
    }
}
```

## Cost Comparison

### Local Docker Jenkins
- **Cost**: $0
- **Maintenance**: You manage
- **Best for**: Testing, development

### AWS EC2 Jenkins
- **Cost**: ~$30-50/month (t3.medium)
- **Maintenance**: You manage
- **Best for**: Small team, full control

### Jenkins on AWS ECS/EKS
- **Cost**: ~$50-100/month
- **Maintenance**: AWS manages infrastructure
- **Best for**: High availability needs

### Managed CI/CD (Comparison)
- **GitHub Actions**: $0-10/month
- **Bitbucket Pipelines**: $0-10/month
- **AWS CodePipeline**: $1/pipeline/month

## Next Steps

1. **Start Jenkins locally**: `docker run jenkins/jenkins:lts`
2. **Create first pipeline**: Use `Jenkinsfile` from repo
3. **Test deployment**: Run UI pipeline first (fastest)
4. **Add webhooks**: Auto-trigger on git push
5. **Monitor builds**: Set up email/Slack notifications

## Files Created

```
rfi_ai-platform/
├── Jenkinsfile              # Complete system pipeline
├── Jenkinsfile.ui           # UI-only pipeline
├── Jenkinsfile.lambda       # Lambda-only pipeline
├── Jenkinsfile.java         # Java API-only pipeline
└── docs/
    └── JENKINS-SETUP.md     # This guide
```

## Quick Commands Reference

```bash
# Start Jenkins
docker run -d --name jenkins -p 8080:8080 jenkins/jenkins:lts

# Stop Jenkins
docker stop jenkins

# Restart Jenkins
docker restart jenkins

# View logs
docker logs -f jenkins

# Execute command in Jenkins
docker exec jenkins <command>

# Backup Jenkins
docker cp jenkins:/var/jenkins_home ./jenkins_backup

# Restore Jenkins
docker cp ./jenkins_backup jenkins:/var/jenkins_home
```
