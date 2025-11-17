# Jenkins on AWS EC2 - Quick Setup Guide

## Overview

This guide helps you deploy a production-ready Jenkins server on AWS EC2 with:
- **Instance**: t3.medium (2 vCPU, 4GB RAM, 30GB storage)
- **OS**: Amazon Linux 2023
- **Jenkins**: Latest LTS version with Docker support
- **IAM**: Instance profile with AWS service permissions
- **Cost**: ~$30-40/month (can stop when not in use to save costs)

## Quick Deploy

```bash
cd deployment
./deploy-jenkins-aws.sh
```

The script will:
1. ✅ Create SSH key pair (jenkins-key.pem)
2. ✅ Create security group (ports 8080, 22, 50000)
3. ✅ Create IAM role with AWS permissions
4. ✅ Launch EC2 instance with Jenkins installed
5. ✅ Configure Docker, Git, Maven, Node.js
6. ✅ Save instance info to jenkins-instance-info.txt

**Wait 5 minutes** for installation to complete.

## Access Jenkins

### Get Instance IP

```bash
# Instance info saved during deployment
cat jenkins-instance-info.txt

# Or query AWS
aws ec2 describe-instances \
    --filters "Name=tag:Name,Values=jenkins-server" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
```

### Get Initial Admin Password

```bash
# SSH to instance
ssh -i jenkins-key.pem ec2-user@<PUBLIC_IP>

# Get password
sudo cat /var/lib/jenkins/secrets/initialAdminPassword

# Or check the info file
cat ~/jenkins-info.txt
```

### Open Jenkins

1. Open browser: `http://<PUBLIC_IP>:8080`
2. Enter initial admin password
3. Click "Install suggested plugins"
4. Create admin user
5. Start using Jenkins!

## Configure Pipelines

### 1. Install Additional Plugins

**Manage Jenkins → Plugins → Available Plugins:**
- AWS Steps
- Docker Pipeline
- Amazon ECR
- Pipeline: AWS Steps
- NodeJS Plugin

### 2. Configure Git Repository

**New Item → Pipeline:**
- Name: `sam-ai-platform`
- Pipeline script from SCM
- SCM: Git
- Repository URL: `https://github.com/billqhan/sam_ai_platform.git`
- Branch: `*/main`
- Script Path: `Jenkinsfile`

### 3. Configure Node.js (for UI builds)

**Manage Jenkins → Tools → NodeJS installations:**
- Name: `node-18`
- Version: NodeJS 18.x
- Install automatically: ✅

### 4. AWS Credentials (Optional)

The instance uses an IAM role, so AWS CLI commands work automatically. But if you need explicit credentials:

**Manage Jenkins → Credentials → System → Global → Add Credentials:**
- Kind: AWS Credentials
- ID: `aws-credentials`
- Access Key ID: (your key)
- Secret Access Key: (your secret)

## Create Pipeline Jobs

### Complete System Pipeline

```bash
# In Jenkins UI
New Item → "Complete System Deploy" → Pipeline
Pipeline script from SCM
Repository: https://github.com/billqhan/sam_ai_platform.git
Script Path: Jenkinsfile
```

### UI Only Pipeline

```bash
New Item → "UI Deploy" → Pipeline
Script Path: Jenkinsfile.ui
```

### Lambda Only Pipeline

```bash
New Item → "Lambda Deploy" → Pipeline
Script Path: Jenkinsfile.lambda
```

### Java API Pipeline

```bash
New Item → "Java API Deploy" → Pipeline
Script Path: Jenkinsfile.java
```

## Test Deployment

### 1. Test UI Pipeline

```bash
# In Jenkins, click "Build Now" on "UI Deploy" job
# Should complete in ~5 minutes
```

### 2. Test Lambda Pipeline

```bash
# Click "Build with Parameters"
# Select Lambda: "all" or specific one
# Should complete in ~7 minutes
```

### 3. Test Java API Pipeline

```bash
# Click "Build Now" on "Java API Deploy" job
# Should complete in ~15 minutes
```

### 4. Test Complete System

```bash
# Click "Build Now" on "Complete System Deploy" job
# Should detect changes and build only affected components
# Full deploy: ~20-30 minutes
```

## Manage Instance

### View Logs

```bash
# SSH to instance
ssh -i jenkins-key.pem ec2-user@<PUBLIC_IP>

# Jenkins logs
sudo journalctl -u jenkins -f

# Docker logs
sudo docker logs -f <container-name>
```

### Stop Instance (Save Costs)

```bash
# Stop when not in use
aws ec2 stop-instances --instance-ids <INSTANCE_ID>

# Start again later
aws ec2 start-instances --instance-ids <INSTANCE_ID>

# Get new public IP after start
aws ec2 describe-instances \
    --instance-ids <INSTANCE_ID> \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text
```

### Backup Jenkins

```bash
# SSH to instance
ssh -i jenkins-key.pem ec2-user@<PUBLIC_IP>

# Backup Jenkins home
sudo tar -czf jenkins-backup-$(date +%Y%m%d).tar.gz /var/lib/jenkins/

# Download backup
exit
scp -i jenkins-key.pem ec2-user@<PUBLIC_IP>:~/jenkins-backup-*.tar.gz .
```

### Restore Jenkins

```bash
# Upload backup
scp -i jenkins-key.pem jenkins-backup-*.tar.gz ec2-user@<PUBLIC_IP>:~

# SSH and restore
ssh -i jenkins-key.pem ec2-user@<PUBLIC_IP>
sudo systemctl stop jenkins
sudo tar -xzf jenkins-backup-*.tar.gz -C /
sudo chown -R jenkins:jenkins /var/lib/jenkins/
sudo systemctl start jenkins
```

## Security Recommendations

### 1. Restrict SSH Access

```bash
# Update security group to allow SSH only from your IP
aws ec2 authorize-security-group-ingress \
    --group-id <SG_ID> \
    --protocol tcp --port 22 \
    --cidr <YOUR_IP>/32
```

### 2. Use HTTPS (Optional)

Install nginx with Let's Encrypt:

```bash
sudo dnf install nginx certbot python3-certbot-nginx -y
sudo certbot --nginx -d jenkins.yourdomain.com
```

Update Jenkins to run behind nginx proxy.

### 3. Enable Jenkins Security

**Manage Jenkins → Security:**
- Authorization: Matrix-based security
- Enable CSRF Protection: ✅
- Prevent Cross Site Request Forgery: ✅

## Troubleshooting

### Jenkins Not Starting

```bash
# Check status
sudo systemctl status jenkins

# View logs
sudo journalctl -u jenkins -n 50

# Restart
sudo systemctl restart jenkins
```

### Docker Permission Denied

```bash
# Add jenkins user to docker group
sudo usermod -aG docker jenkins
sudo systemctl restart jenkins
```

### Out of Memory

```bash
# Edit Jenkins Java options
sudo vi /etc/sysconfig/jenkins
# Change: JENKINS_JAVA_OPTIONS="-Xmx4096m -Xms1024m"

sudo systemctl restart jenkins
```

### Instance Type Too Small

```bash
# Stop instance
aws ec2 stop-instances --instance-ids <INSTANCE_ID>

# Change instance type
aws ec2 modify-instance-attribute \
    --instance-id <INSTANCE_ID> \
    --instance-type t3.large

# Start instance
aws ec2 start-instances --instance-ids <INSTANCE_ID>
```

## Cost Optimization

### Monthly Costs

| Component | Cost |
|-----------|------|
| t3.medium instance (24/7) | ~$30 |
| 30GB gp3 storage | ~$2.40 |
| Data transfer (est.) | ~$5 |
| **Total** | **~$37/month** |

### Save Money

1. **Stop when not in use**: $30/month → $10/month (8h/day usage)
2. **Use Spot Instances**: Save up to 70% (risk of interruption)
3. **Smaller instance**: t3.small ($15/month) for light usage
4. **Scheduled start/stop**: Lambda function to auto-stop overnight

### Auto-Stop Schedule (Optional)

```bash
# Create Lambda to stop at 6 PM, start at 8 AM weekdays
# CloudWatch Events to trigger Lambda
# Saves ~$12/month
```

## Cost Comparison

| Solution | Monthly Cost | Setup Time | Maintenance |
|----------|--------------|------------|-------------|
| **Jenkins on EC2** | $30-40 | 10 min | Medium |
| **Bitbucket Pipelines** | $0-10 | 5 min | Low |
| **GitHub Actions** | $0-10 | 5 min | Low |
| **AWS CodePipeline** | $1-5 | 30 min | Low |

**Recommendation**: 
- Use Bitbucket Pipelines for simplicity and cost
- Use Jenkins EC2 for testing/comparison or complex workflows

## Clean Up

### Terminate Instance

```bash
aws ec2 terminate-instances --instance-ids <INSTANCE_ID>
```

### Delete Resources

```bash
# Delete security group
aws ec2 delete-security-group --group-id <SG_ID>

# Delete key pair
aws ec2 delete-key-pair --key-name jenkins-key
rm jenkins-key.pem

# Delete IAM role
aws iam remove-role-from-instance-profile \
    --instance-profile-name JenkinsEC2Role \
    --role-name JenkinsEC2Role
aws iam delete-instance-profile --instance-profile-name JenkinsEC2Role
aws iam detach-role-policy --role-name JenkinsEC2Role --policy-arn <ARN>
aws iam delete-role --role-name JenkinsEC2Role
```

## Next Steps

1. ✅ Deploy Jenkins: `./deploy-jenkins-aws.sh`
2. ✅ Access Jenkins: `http://<PUBLIC_IP>:8080`
3. ✅ Install plugins
4. ✅ Create pipeline jobs
5. ✅ Test UI deployment
6. ✅ Test Lambda deployment
7. ✅ Test Java API deployment
8. ✅ Test complete system
9. 📊 Compare with Bitbucket Pipelines
10. 🚀 Migrate to Bitbucket for production

## Support

- Jenkins Documentation: https://www.jenkins.io/doc/
- AWS EC2 Guide: https://docs.aws.amazon.com/ec2/
- Pipeline Syntax: https://www.jenkins.io/doc/book/pipeline/syntax/

## Migration to Bitbucket

Once you've tested Jenkins and are ready to migrate to Bitbucket:

1. Create Bitbucket repository
2. Push code from GitHub
3. Create `bitbucket-pipelines.yml` (see docs/JENKINS-SETUP.md)
4. Configure AWS credentials in Bitbucket
5. Test pipelines
6. Terminate Jenkins instance
