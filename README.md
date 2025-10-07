# AI-Powered RFP Response Agent

An automated system that retrieves government contracting opportunities from SAM.gov, processes them using AWS Bedrock AI, and generates match reports to identify relevant business opportunities.

## Development Methodology

This project was developed using Kiro's spec-driven development methodology, following a systematic approach from requirements gathering through design to implementation. The complete development process is documented in the [project specifications](.kiro/specs/ai-rfp-response-agent/README.md), which includes:

- **Requirements Analysis**: 11 detailed requirements with EARS format acceptance criteria covering the complete system workflow
- **System Design**: Comprehensive serverless architecture design using AWS services with event-driven processing
- **Implementation Planning**: 11 major tasks with 40+ actionable sub-tasks for incremental development

The spec documents provide full traceability from business requirements to implementation tasks, ensuring systematic and well-documented development. For detailed information about the development process and methodology, see the [spec summary](.kiro/specs/ai-rfp-response-agent/README.md).

## Architecture

The system uses a serverless, event-driven architecture built on AWS:

- **Lambda Functions**: Process data at each stage of the pipeline
- **S3 Buckets**: Store raw data, processed results, and generated reports
- **SQS**: Queue opportunities for AI processing
- **Bedrock**: AI-powered opportunity matching and analysis
- **EventBridge**: Schedule automated tasks

## Project Structure

```
├── README.md                       # This file
├── .kiro/specs/ai-rfp-response-agent/  # Project specifications
│   ├── requirements.md             # Feature requirements
│   ├── design.md                   # System design
│   └── tasks.md                    # Implementation tasks
├── .github/
│   └── workflows/
│       └── deploy.yml              # GitHub Actions CI/CD (manual trigger only)
├── infrastructure/                 # Infrastructure as Code
│   ├── cloudformation/
│   │   ├── main-template.yaml      # Main CloudFormation template
│   │   ├── master-template.yaml    # Master template
│   │   ├── template.yaml           # Legacy template
│   │   ├── lambda-functions.yaml   # Lambda function definitions
│   │   ├── s3-bucket-policies.yaml # S3 bucket configurations
│   │   ├── s3-event-notifications.yaml  # S3 event triggers
│   │   ├── iam-security-policies.yaml   # IAM roles and policies
│   │   ├── eventbridge-rules.yaml  # EventBridge scheduling
│   │   ├── monitoring-alerting.yaml     # CloudWatch monitoring
│   │   ├── parameters-dev.json     # Development parameters
│   │   ├── parameters-prod.json    # Production parameters
│   │   ├── README.md               # Infrastructure documentation
│   │   ├── MONITORING.md           # Monitoring guide
│   │   └── SECURITY.md             # Security documentation
│   ├── scripts/
│   │   ├── deploy.sh               # Unix deployment script
│   │   ├── deploy.ps1              # PowerShell deployment script
│   │   ├── manage-config.sh        # Configuration management
│   │   ├── package-lambdas.sh      # Lambda packaging
│   │   └── rollback.sh             # Rollback script
│   └── DEPLOYMENT.md               # Deployment documentation
├── reports/                        # Task completion reports
│   ├── task-1-completion-report.md
│   ├── task-2-completion-report.md
│   └── ... (additional task reports)
└── src/
    ├── lambdas/                    # Lambda function implementations
    │   ├── sam-gov-daily-download/
    │   │   ├── handler.py          # Main Lambda handler
    │   │   ├── lambda_function.py  # Lambda entry point
    │   │   ├── requirements.txt    # Dependencies
    │   │   └── test_lambda.py      # Unit tests
    │   ├── sam-json-processor/
    │   │   ├── handler.py          # Processing logic
    │   │   ├── requirements.txt    # Dependencies
    │   │   ├── pytest.ini          # Test configuration
    │   │   ├── test_handler.py     # Handler tests
    │   │   └── test_opportunity_processing.py  # Processing tests
    │   ├── sam-sqs-generate-match-reports/
    │   │   ├── handler.py          # Match report generation
    │   │   ├── requirements.txt    # Dependencies
    │   │   └── test_handler.py     # Unit tests
    │   ├── sam-produce-user-report/
    │   │   ├── handler.py          # Report generation handler
    │   │   ├── report_generator.py # Report generation logic
    │   │   ├── template_manager.py # Template management
    │   │   └── requirements.txt    # Dependencies
    │   ├── sam-produce-web-reports/
    │   │   ├── handler.py          # Web report handler
    │   │   ├── dashboard_generator.py  # Dashboard creation
    │   │   ├── data_aggregator.py  # Data aggregation
    │   │   └── requirements.txt    # Dependencies
    │   └── sam-merge-and-archive-result-logs/
    │       ├── handler.py          # Log merging handler
    │       └── requirements.txt    # Dependencies
    └── shared/                     # Shared utilities and libraries
        ├── __init__.py             # Package initialization
        ├── aws_clients.py          # AWS service clients
        ├── bedrock_utils.py        # Bedrock AI utilities
        ├── config.py               # Configuration management
        ├── dlq_handler.py          # Dead letter queue handling
        ├── error_handling.py       # Error handling and retry logic
        ├── logging_config.py       # Structured logging
        ├── metrics.py              # CloudWatch metrics
        ├── sqs_processor.py        # SQS message processing
        ├── sqs_utils.py            # SQS utilities
        ├── tracing.py              # X-Ray tracing
        └── tests/                  # Shared utility tests
```

## Getting Started

### Prerequisites

- AWS CLI configured with appropriate permissions
- Python 3.11+
- SAM.gov API key

### Environment Variables

Each Lambda function requires specific environment variables. See `src/shared/config.py` for the complete list.

Key variables:
- `SAM_API_KEY`: API key for SAM.gov access
- `KNOWLEDGE_BASE_ID`: Bedrock Knowledge Base ID
- `ENVIRONMENT`: Environment name (dev/staging/prod)

### Deployment

1. Set up your environment variables
2. Run the deployment script:

**Unix/Linux/macOS:**
```bash
./infrastructure/scripts/deploy.sh [environment] [sam-api-key]
```

**Windows PowerShell:**
```powershell
.\infrastructure\scripts\deploy.ps1 [environment] [sam-api-key]
```

Additional deployment utilities:
- `manage-config.sh` - Configuration management
- `package-lambdas.sh` - Lambda function packaging
- `rollback.sh` - Rollback to previous deployment

See `infrastructure/DEPLOYMENT.md` for detailed deployment instructions.

## Development

### Shared Utilities

The `src/shared/` directory contains common utilities used across all Lambda functions:

- **AWS Clients**: Centralized AWS service client management with retry logic
- **Bedrock Utils**: AI-powered opportunity matching utilities
- **Logging**: Structured JSON logging for CloudWatch
- **Error Handling**: Consistent error handling with retry strategies
- **Configuration**: Environment variable management and constants
- **Metrics**: CloudWatch metrics collection
- **SQS Processing**: Message queue processing utilities
- **Tracing**: X-Ray distributed tracing
- **DLQ Handler**: Dead letter queue management

### Adding New Lambda Functions

1. Create a new directory under `src/lambdas/`
2. Add `requirements.txt` with dependencies
3. Create `handler.py` with your main logic
4. Import shared utilities: `from shared import aws_clients, get_logger, config`
5. Use the error handling decorator: `@handle_lambda_error`
6. Add unit tests following the existing pattern

### Testing

Each Lambda function includes unit tests. Run tests using:

```bash
# For individual functions
cd src/lambdas/[function-name]
python -m pytest

# For shared utilities
cd src/shared
python -m pytest tests/
```

### CI/CD Pipeline

The project uses GitHub Actions for continuous integration and deployment:
- `.github/workflows/deploy.yml` - Manual deployment workflow
- **Manual trigger only** - No automatic deployments on push/PR
- Runs validation, tests, packages Lambda functions, and deploys to AWS
- Can be triggered manually from GitHub Actions UI with environment selection

To run a manual deployment:
1. Go to your GitHub repository → Actions tab
2. Select "Deploy AI-powered RFP Response Agent"
3. Click "Run workflow"
4. Choose your target environment (dev/staging/prod)

### Task Reports

Implementation progress is tracked in the `reports/` directory:
- Task completion reports document the implementation of each feature
- Reports include implementation details, testing results, and deployment notes

## Monitoring

The system includes comprehensive logging and monitoring:

- Structured JSON logs in CloudWatch
- Correlation IDs for request tracing
- Error categorization and retry logic
- Performance metrics and alerting

## Security

- IAM roles with least privilege access
- Encryption at rest and in transit
- Secure API key management
- No PII in logs or temporary files