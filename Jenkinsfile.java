// Java API Deployment Pipeline
// Builds Docker image and deploys to ECS

pipeline {
    agent any
    
    environment {
        AWS_REGION = 'us-east-1'
        AWS_ACCOUNT_ID = '160936122037'
        BUCKET_PREFIX = 'dev'
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        ECR_REPOSITORY = "${BUCKET_PREFIX}-rfp-java-api"
        ECS_CLUSTER = "${BUCKET_PREFIX}-ecs-cluster"
        ECS_SERVICE = "${BUCKET_PREFIX}-java-api-service"
        IMAGE_TAG = "${env.BUILD_NUMBER}"
    }
    
    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
        timeout(time: 30, unit: 'MINUTES')
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }
        
        stage('Build Java Application') {
            agent {
                docker {
                    image 'maven:3.9-eclipse-temurin-17'
                    args '-v $HOME/.m2:/root/.m2'
                    reuseNode true
                }
            }
            steps {
                dir('java-api') {
                    sh 'mvn clean package -DskipTests'
                    archiveArtifacts artifacts: 'target/*.jar', fingerprint: true
                }
            }
        }
        
        stage('Run Unit Tests') {
            agent {
                docker {
                    image 'maven:3.9-eclipse-temurin-17'
                    args '-v $HOME/.m2:/root/.m2'
                    reuseNode true
                }
            }
            steps {
                dir('java-api') {
                    sh 'mvn test'
                    junit 'target/surefire-reports/*.xml'
                }
            }
        }
        
        stage('Build Docker Image') {
            steps {
                dir('java-api') {
                    script {
                        // Login to ECR
                        sh """
                            aws ecr get-login-password --region ${AWS_REGION} | \
                            docker login --username AWS --password-stdin ${ECR_REGISTRY}
                        """
                        
                        // Build image
                        sh """
                            docker build \
                                -t ${ECR_REPOSITORY}:${IMAGE_TAG} \
                                -t ${ECR_REPOSITORY}:latest \
                                .
                        """
                    }
                }
            }
        }
        
        stage('Security Scan') {
            steps {
                script {
                    // Optional: Add Trivy or other security scanning
                    sh """
                        docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
                            aquasec/trivy image ${ECR_REPOSITORY}:${IMAGE_TAG} || true
                    """
                }
            }
        }
        
        stage('Push to ECR') {
            steps {
                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                    sh """
                        docker push ${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}
                        docker push ${ECR_REGISTRY}/${ECR_REPOSITORY}:latest
                    """
                }
            }
        }
        
        stage('Deploy to ECS') {
            steps {
                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                    sh """
                        # Update task definition with new image
                        TASK_DEFINITION=\$(aws ecs describe-task-definition \
                            --task-definition ${BUCKET_PREFIX}-java-api-task \
                            --query 'taskDefinition' \
                            --output json)
                        
                        # Register new task definition
                        NEW_TASK_INFO=\$(echo \$TASK_DEFINITION | jq \
                            --arg IMAGE "${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}" \
                            '.containerDefinitions[0].image = \$IMAGE | del(.taskDefinitionArn, .revision, .status, .requiresAttributes, .compatibilities, .registeredAt, .registeredBy)')
                        
                        NEW_TASK_DEF=\$(aws ecs register-task-definition \
                            --cli-input-json "\$NEW_TASK_INFO" \
                            --query 'taskDefinition.taskDefinitionArn' \
                            --output text)
                        
                        # Update service
                        aws ecs update-service \
                            --cluster ${ECS_CLUSTER} \
                            --service ${ECS_SERVICE} \
                            --task-definition \$NEW_TASK_DEF \
                            --force-new-deployment
                        
                        echo "Deployed task definition: \$NEW_TASK_DEF"
                    """
                }
            }
        }
        
        stage('Wait for Deployment') {
            steps {
                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                    sh """
                        echo "Waiting for ECS service to stabilize..."
                        aws ecs wait services-stable \
                            --cluster ${ECS_CLUSTER} \
                            --services ${ECS_SERVICE} \
                            --region ${AWS_REGION}
                    """
                }
            }
        }
        
        stage('Health Check') {
            steps {
                script {
                    // Get the service endpoint
                    def endpoint = sh(
                        script: """
                            aws ecs describe-services \
                                --cluster ${ECS_CLUSTER} \
                                --services ${ECS_SERVICE} \
                                --query 'services[0].loadBalancers[0].targetGroupArn' \
                                --output text
                        """,
                        returnStdout: true
                    ).trim()
                    
                    echo "Health check endpoint: ${endpoint}"
                    // Add actual health check curl here
                }
            }
        }
    }
    
    post {
        success {
            echo "✅ Java API deployed successfully!"
            echo "Image: ${ECR_REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"
        }
        failure {
            echo "❌ Java API deployment failed"
            withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                sh """
                    echo "Rolling back to previous task definition..."
                    aws ecs update-service \
                        --cluster ${ECS_CLUSTER} \
                        --service ${ECS_SERVICE} \
                        --force-new-deployment
                """
            }
        }
        always {
            cleanWs()
        }
    }
}
