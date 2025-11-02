# Deployment Scripts Guide

This directory contains all deployment and operational scripts for the AI-Powered RFP Response Agent.

## 🚀 Main Deployment Scripts

### Primary Deployment (Recommended)

- **`deploy-complete-stack.ps1`** - **MAIN DEPLOYMENT SCRIPT**
  - Complete orchestration: infrastructure + all lambdas + configuration + validation
  - Includes error handling, progress tracking, and skip flags
  - **Usage:** `.\deploy-complete-stack.ps1 -StackName ai-rfp-response-agent-dev -BucketPrefix l3harris-qhan -Region us-east-1`
  - **Flags:** `-SkipInfra`, `-SkipLambdas`, `-SkipConfig`, `-SkipValidation`

### Component Deployment Scripts

- **`deploy-all-lambdas.ps1`** - Deploy all 7 Lambda functions
  - Called by `deploy-complete-stack.ps1`
  - Can be run standalone for Lambda-only updates
  
- **`generate-reports-and-notify.ps1`** - Run reporting workflow
  - Executes: merge logs → generate dashboard → send email
  - Called by `deploy-complete-stack.ps1` for validation
  - Can be run standalone for manual reporting

## 📊 Workflow Execution Scripts

### Full Workflow

- **`run-complete-workflow.ps1`** - Execute entire RFP pipeline
  - Downloads opportunities from SAM.gov
  - Processes and extracts individual opportunities
  - Runs AI matching against company profiles
  - Generates reports and sends notifications
  - **Usage:** `.\run-complete-workflow.ps1 -OpportunitiesToProcess 10`

- **`trigger-workflow.ps1`** - Manual workflow trigger
  - Triggers analysis workflow with Bedrock AI
  - Finds latest SAM file and initiates processing
  - **Usage:** `.\trigger-workflow.ps1 -BucketPrefix l3harris-qhan`

### Batch Operations

- **`trigger-batch-matching.ps1`** - Process opportunities in batches
  - Useful for processing large numbers of opportunities
  - Controls batch size and parallelism

## 🛠️ Utility Scripts

### Infrastructure Management

- **`cloudformation-update-command.ps1`** - Manual CloudFormation update
  - Updates specific CloudFormation stacks
  - **Note:** Prefer using `deploy-complete-stack.ps1` instead

- **`cloudformation-update-command.sh`** - Bash version for Linux/Mac

### Lambda-Specific

- **`deploy-web-reports-lambda.ps1`** - Deploy only web reports Lambda
  - Standalone deployment for quick updates
  - Included in `deploy-all-lambdas.ps1`

### Monitoring & Troubleshooting

- **`check-dlq-status.ps1`** - Check Dead Letter Queue status
  - Monitors failed message processing
  - Useful for troubleshooting

- **`fix-dlq-issue.ps1`** - Fix DLQ processing issues
  - Automated remediation for common DLQ problems

## 📂 Subdirectories

### `sam-sqs-generate-match-reports/`

Contains Lambda function code and deployment scripts for the match reports generator:
- `lambda_function.py` - Main Lambda handler
- `deploy-*.ps1` - Various fix deployment scripts
- Documentation for specific fixes (citation format, imports, null safety)

## 🎯 Common Usage Patterns

### Full Clean Deploy (Recommended)
```powershell
.\deploy-complete-stack.ps1 -StackName ai-rfp-response-agent-dev -BucketPrefix l3harris-qhan -Region us-east-1
```

### Deploy Only Lambdas (Code Changes)
```powershell
.\deploy-complete-stack.ps1 -StackName ai-rfp-response-agent-dev -BucketPrefix l3harris-qhan -SkipInfra -SkipValidation
# OR
.\deploy-all-lambdas.ps1
```

### Run Daily Processing Workflow
```powershell
.\run-complete-workflow.ps1 -OpportunitiesToProcess 10
```

### Generate Reports Manually
```powershell
.\generate-reports-and-notify.ps1
```

### Validate Deployment
```powershell
.\generate-reports-and-notify.ps1  # Should return 200 status codes
```

## 📝 Documentation Files

- **`DEPLOYMENT-SUMMARY.md`** - Detailed deployment history and notes
- **`DLQ-ISSUE-FIX-README.md`** - Documentation for DLQ troubleshooting
- **`sam-sqs-generate-match-reports/README.md`** - Match reports Lambda documentation
- **`sam-sqs-generate-match-reports/*-FIX-README.md`** - Specific fix documentation

## ⚙️ Prerequisites

All scripts require:
- AWS CLI configured with appropriate credentials
- PowerShell 5.1+ (Windows) or PowerShell Core (cross-platform)
- Proper IAM permissions for Lambda, S3, CloudFormation operations
- Stack name: `ai-rfp-response-agent-dev`
- Bucket prefix: `l3harris-qhan`
- Region: `us-east-1`

## 🔍 Troubleshooting

1. **Deployment fails:** Check CloudFormation console for detailed error messages
2. **Lambda updates fail:** Verify IAM permissions and function names
3. **No reports generated:** Check Lambda logs in CloudWatch
4. **DLQ messages:** Use `check-dlq-status.ps1` to investigate

For detailed troubleshooting, see `../docs/troubleshooting/` directory.

## 📌 Notes

- Always use `deploy-complete-stack.ps1` for production deployments
- Component scripts are useful for development and quick updates
- Validate changes with `generate-reports-and-notify.ps1` before committing
- Monitor CloudWatch logs for Lambda execution details
