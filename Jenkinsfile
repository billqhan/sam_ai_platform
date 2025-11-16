// Complete System Pipeline
// Builds and deploys all components: UI, Lambda, Java API

pipeline {
    agent any
    
    environment {
        AWS_REGION = 'us-east-1'
        ENVIRONMENT = 'dev'
        BUCKET_PREFIX = 'dev'
        AWS_ACCOUNT_ID = '160936122037'
        ECR_REGISTRY = "${AWS_ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
        CLOUDFRONT_DISTRIBUTION = 'EZ3JUM700S8C6'
    }
    
    options {
        buildDiscarder(logRotator(numToKeepStr: '10'))
        timestamps()
        timeout(time: 1, unit: 'HOURS')
    }
    
    stages {
        stage('Checkout') {
            steps {
                checkout scm
                sh 'git log -1'
            }
        }
        
        stage('Detect Changes') {
            steps {
                script {
                    def changes = sh(
                        script: 'git diff --name-only HEAD~1 HEAD || echo "all"',
                        returnStdout: true
                    ).trim()
                    
                    env.BUILD_UI = changes.contains('ui/') || changes == 'all' ? 'true' : 'false'
                    env.BUILD_LAMBDA = changes.contains('src/lambdas/') || changes == 'all' ? 'true' : 'false'
                    env.BUILD_JAVA = changes.contains('java-api/') || changes == 'all' ? 'true' : 'false'
                    env.BUILD_INFRA = changes.contains('infrastructure/') || changes == 'all' ? 'true' : 'false'
                    
                    echo "Changes detected:"
                    echo "  UI: ${env.BUILD_UI}"
                    echo "  Lambda: ${env.BUILD_LAMBDA}"
                    echo "  Java API: ${env.BUILD_JAVA}"
                    echo "  Infrastructure: ${env.BUILD_INFRA}"
                }
            }
        }
        
        stage('Build & Deploy') {
            parallel {
                stage('UI Pipeline') {
                    when {
                        environment name: 'BUILD_UI', value: 'true'
                    }
                    stages {
                        stage('Build UI') {
                            agent {
                                docker {
                                    image 'node:18'
                                    reuseNode true
                                }
                            }
                            steps {
                                dir('ui') {
                                    sh 'npm ci'
                                    sh 'npm run build'
                                    stash name: 'ui-dist', includes: 'dist/**'
                                }
                            }
                        }
                        
                        stage('Deploy UI to S3') {
                            steps {
                                unstash 'ui-dist'
                                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                                    s3Delete(bucket: "${BUCKET_PREFIX}-sam-website-${ENVIRONMENT}", path: '')
                                    s3Upload(
                                        bucket: "${BUCKET_PREFIX}-sam-website-${ENVIRONMENT}",
                                        path: '',
                                        includePathPattern: '**/*',
                                        workingDir: 'ui/dist'
                                    )
                                }
                            }
                        }
                        
                        stage('Invalidate CloudFront') {
                            steps {
                                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                                    sh """
                                        aws cloudfront create-invalidation \
                                            --distribution-id ${CLOUDFRONT_DISTRIBUTION} \
                                            --paths "/*"
                                    """
                                }
                            }
                        }
                    }
                }
                
                stage('Lambda Pipeline') {
                    when {
                        environment name: 'BUILD_LAMBDA', value: 'true'
                    }
                    agent {
                        docker {
                            image 'python:3.11'
                            reuseNode true
                        }
                    }
                    steps {
                        dir('deployment') {
                            sh 'chmod +x deploy-all-lambdas.sh'
                            withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                                sh './deploy-all-lambdas.sh'
                            }
                        }
                    }
                }
                
                stage('Java API Pipeline') {
                    when {
                        environment name: 'BUILD_JAVA', value: 'true'
                    }
                    stages {
                        stage('Build Java') {
                            agent {
                                docker {
                                    image 'maven:3.9-eclipse-temurin-17'
                                    reuseNode true
                                }
                            }
                            steps {
                                dir('java-api') {
                                    sh 'mvn clean package -DskipTests'
                                    stash name: 'java-jar', includes: 'target/*.jar'
                                }
                            }
                        }
                        
                        stage('Build Docker Image') {
                            steps {
                                dir('java-api') {
                                    unstash 'java-jar'
                                    script {
                                        docker.withRegistry("https://${ECR_REGISTRY}", "ecr:${AWS_REGION}:aws-credentials") {
                                            def image = docker.build("${BUCKET_PREFIX}-rfp-java-api:${env.BUILD_NUMBER}")
                                            image.push()
                                            image.push('latest')
                                        }
                                    }
                                }
                            }
                        }
                        
                        stage('Deploy to ECS') {
                            steps {
                                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                                    sh """
                                        aws ecs update-service \
                                            --cluster ${BUCKET_PREFIX}-ecs-cluster \
                                            --service ${BUCKET_PREFIX}-java-api-service \
                                            --force-new-deployment
                                    """
                                }
                            }
                        }
                    }
                }
            }
        }
        
        stage('Infrastructure') {
            when {
                environment name: 'BUILD_INFRA', value: 'true'
            }
            steps {
                input message: 'Deploy infrastructure changes?', ok: 'Deploy'
                withAWS(credentials: 'aws-credentials', region: env.AWS_REGION) {
                    sh """
                        aws cloudformation deploy \
                            --template-file infrastructure/cloudformation/lambda-functions.yaml \
                            --stack-name ai-rfp-response-agent-${ENVIRONMENT}-LambdaFunctionsStack \
                            --parameter-overrides \
                                Environment=${ENVIRONMENT} \
                                BucketPrefix=${BUCKET_PREFIX} \
                            --capabilities CAPABILITY_IAM
                    """
                }
            }
        }
        
        stage('Integration Tests') {
            steps {
                sh '''
                    echo "Running integration tests..."
                    curl -f https://d8bbmb3a6jev2.cloudfront.net/ || exit 1
                    curl -f https://3cvymua5c8.execute-api.us-east-1.amazonaws.com/dev/health || exit 1
                '''
            }
        }
    }
    
    post {
        success {
            echo 'Deployment successful! 🎉'
            // Add Slack/email notification here
        }
        failure {
            echo 'Deployment failed! ❌'
            // Add Slack/email notification here
        }
        always {
            cleanWs()
        }
    }
}
