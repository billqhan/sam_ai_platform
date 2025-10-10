#!/bin/bash

# CloudFormation Stack Update Command with Required Parameters
# This updates the Lambda functions with fixed IAM permissions

aws cloudformation update-stack \
  --stack-name ai-rfp-response-agent-phase2-dev \
  --template-body file://infrastructure/cloudformation/lambda-functions.yaml \
  --parameters \
    ParameterKey=Environment,ParameterValue=dev \
    ParameterKey=CompanyName,ParameterValue=L3Harris \
    ParameterKey=CompanyContact,ParameterValue=contact@L3Harris.com \
    ParameterKey=BucketPrefix,ParameterValue=ktest \
    ParameterKey=SamApiKey,UsePreviousValue=true \
    ParameterKey=SqsSamJsonMessagesQueueArn,ParameterValue=arn:aws:sqs:us-east-1:302585542747:ktest-sqs-sam-json-messages-dev \
  --capabilities CAPABILITY_IAM \
  --region us-east-1

echo "CloudFormation stack update initiated..."
echo "Monitor progress with: aws cloudformation describe-stack-events --stack-name ai-rfp-response-agent-phase2-dev --region us-east-1"