#!/bin/bash
# Deploy Jenkins on AWS EC2
# Creates a production-ready Jenkins server with Docker support

set -e

# Configuration
INSTANCE_TYPE="${INSTANCE_TYPE:-m7i-flex.large}"  # Free Tier: 2 vCPU, 1GB RAM (can override with env var)
REGION="us-east-1"
KEY_NAME="jenkins-key"
SECURITY_GROUP_NAME="jenkins-sg"
INSTANCE_NAME="jenkins-server"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }

# Get latest Amazon Linux 2023 AMI
get_latest_ami() {
    aws ec2 describe-images \
        --owners amazon \
        --filters "Name=name,Values=al2023-ami-2023*-x86_64" \
              "Name=state,Values=available" \
        --query 'sort_by(Images, &CreationDate)[-1].ImageId' \
        --output text \
        --region "$REGION"
}

# Create key pair if it doesn't exist
create_key_pair() {
    if aws ec2 describe-key-pairs --key-names "$KEY_NAME" --region "$REGION" &>/dev/null; then
        log_info "Key pair $KEY_NAME already exists"
    else
        log_info "Creating key pair: $KEY_NAME"
        aws ec2 create-key-pair \
            --key-name "$KEY_NAME" \
            --query 'KeyMaterial' \
            --output text \
            --region "$REGION" > "${KEY_NAME}.pem"
        
        chmod 400 "${KEY_NAME}.pem"
        log_success "Key pair created and saved to ${KEY_NAME}.pem"
        log_warning "IMPORTANT: Save this file! You won't be able to download it again."
    fi
}

# Create security group
create_security_group() {
    local vpc_id=$(aws ec2 describe-vpcs \
        --filters "Name=is-default,Values=true" \
        --query 'Vpcs[0].VpcId' \
        --output text \
        --region "$REGION")
    
    if aws ec2 describe-security-groups \
        --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
        --region "$REGION" &>/dev/null | grep -q "$SECURITY_GROUP_NAME"; then
        log_info "Security group $SECURITY_GROUP_NAME already exists"
        SG_ID=$(aws ec2 describe-security-groups \
            --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
            --query 'SecurityGroups[0].GroupId' \
            --output text \
            --region "$REGION")
    else
        log_info "Creating security group: $SECURITY_GROUP_NAME"
        SG_ID=$(aws ec2 create-security-group \
            --group-name "$SECURITY_GROUP_NAME" \
            --description "Security group for Jenkins server" \
            --vpc-id "$vpc_id" \
            --region "$REGION" \
            --query 'GroupId' \
            --output text)
        
        # Add rules
        log_info "Adding security group rules..."
        
        # Jenkins web interface
        aws ec2 authorize-security-group-ingress \
            --group-id "$SG_ID" \
            --protocol tcp --port 8080 \
            --cidr 0.0.0.0/0 \
            --region "$REGION"
        
        # SSH access
        aws ec2 authorize-security-group-ingress \
            --group-id "$SG_ID" \
            --protocol tcp --port 22 \
            --cidr 0.0.0.0/0 \
            --region "$REGION"
        
        # Jenkins agent port
        aws ec2 authorize-security-group-ingress \
            --group-id "$SG_ID" \
            --protocol tcp --port 50000 \
            --cidr 0.0.0.0/0 \
            --region "$REGION"
        
        log_success "Security group created: $SG_ID"
    fi
}

# Create IAM role for Jenkins
create_iam_role() {
    local role_name="JenkinsEC2Role"
    
    if aws iam get-role --role-name "$role_name" &>/dev/null; then
        log_info "IAM role $role_name already exists"
    else
        log_info "Creating IAM role for Jenkins..."
        
        # Trust policy
        cat > /tmp/jenkins-trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Service": "ec2.amazonaws.com"
      },
      "Action": "sts:AssumeRole"
    }
  ]
}
EOF
        
        aws iam create-role \
            --role-name "$role_name" \
            --assume-role-policy-document file:///tmp/jenkins-trust-policy.json
        
        # Attach policies
        aws iam attach-role-policy \
            --role-name "$role_name" \
            --policy-arn arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryFullAccess
        
        aws iam attach-role-policy \
            --role-name "$role_name" \
            --policy-arn arn:aws:iam::aws:policy/AmazonECS_FullAccess
        
        aws iam attach-role-policy \
            --role-name "$role_name" \
            --policy-arn arn:aws:iam::aws:policy/AmazonS3FullAccess
        
        aws iam attach-role-policy \
            --role-name "$role_name" \
            --policy-arn arn:aws:iam::aws:policy/AWSLambda_FullAccess
        
        aws iam attach-role-policy \
            --role-name "$role_name" \
            --policy-arn arn:aws:iam::aws:policy/CloudFrontFullAccess
        
        # Create instance profile
        aws iam create-instance-profile --instance-profile-name "$role_name"
        aws iam add-role-to-instance-profile \
            --instance-profile-name "$role_name" \
            --role-name "$role_name"
        
        log_success "IAM role created with necessary permissions"
        sleep 10  # Wait for IAM propagation
    fi
}

# User data script to install Jenkins
create_user_data() {
    cat > /tmp/jenkins-userdata.sh <<'EOF'
#!/bin/bash
set -e

# Update system
dnf update -y

# Install Java 17
dnf install java-17-amazon-corretto -y

# Install Jenkins
wget -O /etc/yum.repos.d/jenkins.repo \
    https://pkg.jenkins.io/redhat-stable/jenkins.repo
rpm --import https://pkg.jenkins.io/redhat-stable/jenkins.io-2023.key
dnf install jenkins -y

# Install Docker
dnf install docker -y
usermod -aG docker jenkins
usermod -aG docker ec2-user

# Install Git
dnf install git -y

# Install AWS CLI v2 (already installed on AL2023)
# Configure it to use instance profile
mkdir -p /var/lib/jenkins/.aws
cat > /var/lib/jenkins/.aws/config <<'AWSCONFIG'
[default]
region = us-east-1
output = json
AWSCONFIG
chown -R jenkins:jenkins /var/lib/jenkins/.aws

# Start services
systemctl start docker
systemctl enable docker
systemctl start jenkins
systemctl enable jenkins

# Wait for Jenkins to start
sleep 30

# Get initial admin password
JENKINS_PASSWORD=$(cat /var/lib/jenkins/secrets/initialAdminPassword)

# Create info file
cat > /home/ec2-user/jenkins-info.txt <<INFO
========================================
Jenkins Installation Complete!
========================================

Jenkins URL: http://$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4):8080

Initial Admin Password: $JENKINS_PASSWORD

To SSH into this instance:
ssh -i jenkins-key.pem ec2-user@$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4)

Next Steps:
1. Open Jenkins URL in browser
2. Enter the initial admin password
3. Install suggested plugins
4. Create admin user
5. Configure AWS credentials (will use instance profile automatically)

========================================
INFO

# Install common tools
dnf install -y maven nodejs npm python3 python3-pip

# Configure Jenkins Java options (optimized for m7i-flex.large with 8GB RAM)
cat > /etc/sysconfig/jenkins <<'JENKINSCONF'
JENKINS_JAVA_OPTIONS="-Djava.awt.headless=true -Xmx4096m -Xms1024m"
JENKINSCONF

systemctl restart jenkins

echo "Jenkins installation complete!"
EOF
}

# Launch EC2 instance
launch_instance() {
    log_info "Getting latest Amazon Linux AMI..."
    AMI_ID=$(get_latest_ami)
    log_info "Using AMI: $AMI_ID"
    
    log_info "Creating user data script..."
    create_user_data
    
    log_info "Launching EC2 instance..."
    INSTANCE_ID=$(aws ec2 run-instances \
        --image-id "$AMI_ID" \
        --instance-type "$INSTANCE_TYPE" \
        --key-name "$KEY_NAME" \
        --security-group-ids "$SG_ID" \
        --iam-instance-profile Name=JenkinsEC2Role \
        --user-data file:///tmp/jenkins-userdata.sh \
        --block-device-mappings '[{"DeviceName":"/dev/xvda","Ebs":{"VolumeSize":30,"VolumeType":"gp3"}}]' \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
        --region "$REGION" \
        --query 'Instances[0].InstanceId' \
        --output text)
    
    log_success "Instance launched: $INSTANCE_ID"
    
    log_info "Waiting for instance to be running..."
    aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" --region "$REGION"
    
    # Get public IP
    PUBLIC_IP=$(aws ec2 describe-instances \
        --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].PublicIpAddress' \
        --output text \
        --region "$REGION")
    
    log_success "Instance is running!"
    echo ""
    echo "=========================================="
    echo "  Jenkins Server Details"
    echo "=========================================="
    echo ""
    echo "Instance ID: $INSTANCE_ID"
    echo "Public IP:   $PUBLIC_IP"
    echo "Jenkins URL: http://$PUBLIC_IP:8080"
    echo ""
    echo "SSH Command:"
    echo "  ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP"
    echo ""
    echo "=========================================="
    echo ""
    log_warning "Jenkins is installing... This will take 3-5 minutes."
    log_info "To get the initial admin password, run:"
    echo "  ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP 'sudo cat /var/lib/jenkins/secrets/initialAdminPassword'"
    echo ""
    log_info "Or check the jenkins-info.txt file on the instance:"
    echo "  ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP 'cat ~/jenkins-info.txt'"
    echo ""
    
    # Save instance info
    cat > jenkins-instance-info.txt <<INFO
Jenkins Instance Information
============================

Instance ID: $INSTANCE_ID
Public IP: $PUBLIC_IP
Region: $REGION
Instance Type: $INSTANCE_TYPE

URLs:
- Jenkins: http://$PUBLIC_IP:8080
- SSH: ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP

Get Initial Password:
ssh -i ${KEY_NAME}.pem ec2-user@$PUBLIC_IP 'sudo cat /var/lib/jenkins/secrets/initialAdminPassword'

Stop Instance:
aws ec2 stop-instances --instance-ids $INSTANCE_ID --region $REGION

Start Instance:
aws ec2 start-instances --instance-ids $INSTANCE_ID --region $REGION

Terminate Instance:
aws ec2 terminate-instances --instance-ids $INSTANCE_ID --region $REGION
INFO
    
    log_success "Instance info saved to jenkins-instance-info.txt"
}

# Main execution
main() {
    echo ""
    echo "=========================================="
    echo "  Jenkins on AWS EC2 Deployment"
    echo "=========================================="
    echo ""
    echo "Configuration:"
    echo "  Instance Type: $INSTANCE_TYPE (Free Tier)"
    echo "  Region: $REGION"
    echo "  Key Name: $KEY_NAME"
    echo ""
    echo "Note: Using m7i-flex.large (Free Tier). For smaller instance:"
    echo "      export INSTANCE_TYPE=t3.micro && ./deploy-jenkins-aws.sh"
    echo ""
    
    read -p "Continue with deployment? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deployment cancelled"
        exit 0
    fi
    
    log_info "Starting Jenkins deployment..."
    
    create_key_pair
    create_security_group
    create_iam_role
    launch_instance
    
    echo ""
    log_success "Jenkins deployment initiated successfully!"
    echo ""
    echo "Wait 5 minutes, then access Jenkins at: http://$PUBLIC_IP:8080"
    echo ""
}

main
