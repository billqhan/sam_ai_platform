# AI-Powered RFP Response Agent

An automated system that retrieves government contracting opportunities from SAM.gov, processes them using AWS Bedrock AI, and generates match reports to identify relevant business opportunities.

## Architecture

The system uses a serverless, event-driven architecture built on AWS:

- **Lambda Functions**: Process data at each stage of the pipeline
- **S3 Buckets**: Store raw data, processed results, and generated reports
- **SQS**: Queue opportunities for AI processing
- **Bedrock**: AI-powered opportunity matching and analysis
- **EventBridge**: Schedule automated tasks

## Project Structure

```
├── src/
│   ├── lambdas/                    # Lambda function implementations
│   │   ├── sam-gov-daily-download/
│   │   ├── sam-json-processor/
│   │   ├── sam-sqs-generate-match-reports/
│   │   ├── sam-produce-user-report/
│   │   ├── sam-merge-and-archive-result-logs/
│   │   └── sam-produce-web-reports/
│   └── shared/                     # Shared utilities and libraries
│       ├── aws_clients.py          # AWS service clients
│       ├── logging_config.py       # Structured logging
│       ├── error_handling.py       # Error handling and retry logic
│       └── config.py               # Configuration management
├── infrastructure/                 # Infrastructure as Code
│   ├── cloudformation/
│   │   └── template.yaml
│   └── scripts/
│       └── deploy.sh
└── .kiro/specs/ai-rfp-response-agent/  # Project specifications
    ├── requirements.md
    ├── design.md
    └── tasks.md
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

```bash
./infrastructure/scripts/deploy.sh [environment] [sam-api-key]
```

## Development

### Shared Utilities

The `src/shared/` directory contains common utilities used across all Lambda functions:

- **AWS Clients**: Centralized AWS service client management with retry logic
- **Logging**: Structured JSON logging for CloudWatch
- **Error Handling**: Consistent error handling with retry strategies
- **Configuration**: Environment variable management and constants

### Adding New Lambda Functions

1. Create a new directory under `src/lambdas/`
2. Add `requirements.txt` with dependencies
3. Import shared utilities: `from shared import aws_clients, get_logger, config`
4. Use the error handling decorator: `@handle_lambda_error`

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