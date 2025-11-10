# Deployment Scripts Guide

This directory contains all deployment and operational scripts for the AI-Powered RFP Response Agent.

## 🚀 Main Deployment Scripts

### Primary Deployment (Recommended)

Use the main deployment script at project root:
- **`../deploy-complete.sh`** - **MAIN DEPLOYMENT SCRIPT**
  - Complete orchestration: infrastructure + all lambdas + Java API + UI
  - Sources configuration from `.env.dev`
  - **Usage:** `./deploy-complete.sh` (full) or `./deploy-complete.sh lambda` (Lambda only)
  - **Modules:** `java-api`, `lambda`, `ui`, or omit for full deployment

### Component Deployment Scripts

- **`deploy-all-lambdas.sh`** / **`deploy-all-lambdas.ps1`** - Deploy all Lambda functions
  - Uses S3-based deployment for reliability with large packages
  - Uploads to `ai-rfp-templates-dev` bucket, then updates Lambda functions
  - Sources configuration from `../.env.dev`
  - **Usage:** `./deploy-all-lambdas.sh` (called automatically by deploy-complete.sh)
  
- **`generate-reports-and-notify.ps1`** - Run reporting workflow
  - Executes: merge logs → generate dashboard → send email
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

### Configuration Management

- **`update-sam-api-key.sh`** - Update SAM.gov API key
  - Updates API key in Lambda environment variables
  - **Usage:** `./update-sam-api-key.sh NEW_API_KEY`

- **`auto-generate-report.sh`** - Automated report generation
  - Can be scheduled via cron for automated reporting

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
```bash
# From project root
./deploy-complete.sh
```

### Deploy Only Lambdas (Code Changes)
```bash
# From project root
./deploy-complete.sh lambda
```

### Deploy Specific Modules
```bash
# From project root
./deploy-complete.sh java-api  # Java API only
./deploy-complete.sh ui        # UI only
```

### Run Daily Processing Workflow
```powershell
cd deployment
.\run-complete-workflow.ps1 -OpportunitiesToProcess 10
```

### Generate Reports Manually
```powershell
cd deployment
.\generate-reports-and-notify.ps1
```

### Trigger Manual Workflow
```powershell
cd deployment
.\trigger-workflow.ps1
```

## 📝 Documentation Files

- **`DEPLOYMENT-SUMMARY.md`** - Detailed deployment history and notes
- **`DLQ-ISSUE-FIX-README.md`** - Documentation for DLQ troubleshooting
- **`sam-sqs-generate-match-reports/README.md`** - Match reports Lambda documentation
- **`sam-sqs-generate-match-reports/*-FIX-README.md`** - Specific fix documentation

## ⚙️ Prerequisites

All scripts require:
- AWS CLI configured with appropriate credentials
- PowerShell (for workflow scripts only)
- Bash (for deployment scripts)
- Proper IAM permissions for Lambda, S3, CloudFormation, ECS operations
- Configuration file: `.env.dev` at project root (required)
- Docker (for Java API deployment)

## 🔍 Troubleshooting

1. **Deployment fails:** Check CloudFormation console for detailed error messages
2. **Lambda updates fail:** Verify IAM permissions and S3 bucket `ai-rfp-templates-dev` exists
3. **Configuration errors:** Ensure `.env.dev` exists at project root with all required variables
4. **No reports generated:** Check Lambda logs in CloudWatch
5. **DLQ messages:** Use `check-dlq-status.ps1` to investigate
6. **AWS CLI hangs:** Pager disabled via `AWS_PAGER=""` in `.env.dev`

For detailed troubleshooting, see `../docs/troubleshooting/` directory.

## 📌 Notes

- Always use `../deploy-complete.sh` from project root for deployments
- All configuration is centralized in `.env.dev` - no hardcoded values
- Lambda packages are uploaded to S3 first for reliability with large files
- Monitor CloudWatch logs for Lambda execution details
- Use workflow scripts in this directory for manual testing and operations

### S3 Event Notifications

`configure-s3-notifications.sh` - Configure S3 event notifications for automatic workflow chaining
- Configures 4 S3 buckets to trigger Lambda functions and SQS queues automatically
- Ensures SQS queue uses compatible encryption (SQS-managed, not KMS)
- Enables fully automated workflow: Download → Process → Match → Reports

**Note**: Run this after initial deployment if S3 notifications are not configured.

#### CloudFormation rollback on S3 notifications (FYI)

If you previously deployed `infrastructure/cloudformation/s3-event-notifications.yaml` and see a stack in `UPDATE_ROLLBACK_COMPLETE` with errors like:

- `AWS::SQS::QueuePolicy DELETE_FAILED: Last applied policy cannot be deleted. Please delete other policies applied to this resource before deleting the last applied policy.`

This is benign for runtime and caused by CloudFormation attempting to delete or replace an SQS queue policy while another policy existed. We resolved this by deleting the obsolete stack and keeping the working policy/configuration in place. Going forward:

- Prefer the manual script (`configure-s3-notifications.sh`) for reliability.
- The template now marks the `SqsQueuePolicy` with `DeletionPolicy: Retain` to avoid breaking S3→SQS if the stack is deleted.
- If you do re-enable the CloudFormation template, make sure no external queue policy writers are competing (console/CLI/other stacks).
