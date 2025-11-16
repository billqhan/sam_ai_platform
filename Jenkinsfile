pipeline {
  agent any

  options {
    timestamps()
    ansiColor('xterm')
  }

  parameters {
    choice(name: 'DEPLOY_TARGET', choices: ['none','ecs','eks'], description: 'Where to deploy after build')
    string(name: 'ENVIRONMENT', defaultValue: 'dev', description: 'Environment name (e.g., dev, prod)')
    string(name: 'AWS_REGION', defaultValue: 'us-east-1', description: 'AWS region')
    string(name: 'IMAGE_TAG', defaultValue: 'dev-latest', description: 'Docker image tag (use dev-latest to align with task defs)')
    string(name: 'ECS_SERVICE', defaultValue: 'dev-java-api', description: 'ECS service name (default matches Terraform: <env>-java-api)')
    string(name: 'K8S_NAMESPACE', defaultValue: 'sam-ai', description: 'Kubernetes namespace for EKS deploy')
    string(name: 'K8S_DEPLOYMENT', defaultValue: 'java-api', description: 'Kubernetes deployment name for EKS deploy')
  }

  environment {
    ECR_REPO   = 'sam-ai-java-api'
  }

  stages {
    stage('Checkout') {
      steps { checkout scm }
    }

    stage('Build & Test (Java API)') {
      agent { label 'docker' }
      steps {
        dir('java-api') {
          sh 'chmod +x build.sh || true'
          sh './build.sh'
        }
      }
    }

    stage('Docker Build') {
      agent { label 'docker' }
      steps {
        sh '''
          set -e
          # Build with a local tag first; retag during push
          docker build -t ${ECR_REPO}:${IMAGE_TAG} java-api
        '''
      }
    }

    stage('Push to ECR') {
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-jenkins']]) {
          sh '''
            set -e
            ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
            ECR_URL="$ACCOUNT_ID.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
            aws ecr describe-repositories --repository-names ${ECR_REPO} >/dev/null 2>&1 || aws ecr create-repository --repository-name ${ECR_REPO}
            aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${ECR_URL}
            # Retag local image to ECR URI and push
            docker tag ${ECR_REPO}:${IMAGE_TAG} ${ECR_URL}:${IMAGE_TAG}
            docker push ${ECR_URL}:${IMAGE_TAG}
          '''
        }
      }
    }

    stage('Deploy') {
      when { expression { return params.DEPLOY_TARGET != 'none' } }
      steps {
        withCredentials([[$class: 'AmazonWebServicesCredentialsBinding', credentialsId: 'aws-jenkins']]) {
          script {
            if (params.DEPLOY_TARGET == 'ecs') {
              sh '''
                set -e
                ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
                ECR_URL="$ACCOUNT_ID.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
                CLUSTER="${ENVIRONMENT}-sam-ai-ecs"
                SERVICE="${ECS_SERVICE}"
                # Fallback to <env>-java-api if ECS_SERVICE not provided
                if [ -z "$SERVICE" ]; then SERVICE="${ENVIRONMENT}-java-api"; fi
                # Force new deployment (task def references dev-latest by default)
                aws ecs update-service --cluster "$CLUSTER" --service "$SERVICE" --force-new-deployment --region ${AWS_REGION}
                aws ecs wait services-stable --cluster "$CLUSTER" --services "$SERVICE" --region ${AWS_REGION}
              '''
            } else if (params.DEPLOY_TARGET == 'eks') {
              sh '''
                set -e
                ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
                ECR_URL="$ACCOUNT_ID.dkr.ecr.${AWS_REGION}.amazonaws.com/${ECR_REPO}"
                aws eks update-kubeconfig --name ${ENVIRONMENT}-sam-ai-eks --region ${AWS_REGION}
                kubectl set image deployment/${K8S_DEPLOYMENT} ${K8S_DEPLOYMENT}=${ECR_URL}:${IMAGE_TAG} -n ${K8S_NAMESPACE}
                kubectl rollout status deployment/${K8S_DEPLOYMENT} -n ${K8S_NAMESPACE}
              '''
            }
          }
        }
      }
    }
  }

  post {
    success { echo 'Pipeline completed successfully.' }
    failure { echo 'Pipeline failed.' }
  }
}
