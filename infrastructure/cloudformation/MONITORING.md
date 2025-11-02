# AI RFP Response Agent - Monitoring and Alerting Guide

## Overview

This document describes the comprehensive monitoring and alerting system implemented for the AI-powered RFP Response Agent. The system includes structured logging, X-Ray tracing, custom CloudWatch metrics, and automated alerting.

## Architecture

### Monitoring Components

1. **Structured JSON Logging**: All Lambda functions use standardized JSON logging with correlation IDs
2. **X-Ray Tracing**: End-to-end request tracing across all AWS services
3. **Custom CloudWatch Metrics**: Business-specific metrics for monitoring system performance
4. **CloudWatch Alarms**: Automated alerting for system issues and performance degradation
5. **CloudWatch Dashboard**: Real-time visualization of system health and performance

## Structured Logging

### Log Format

All logs follow a standardized JSON structure:

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "message": "OPPORTUNITY_PROCESSED",
  "correlation_id": "12345678-1234-1234-1234-123456789012",
  "function_name": "sam-sqs-generate-match-reports",
  "function_version": "$LATEST",
  "request_id": "abcd1234-5678-90ef-ghij-klmnopqrstuv",
  "trace_id": "1-5e1b4151-1234567890123456",
  "segment_id": "abcdef1234567890",
  "context": {
    "opportunity_id": "ABC123",
    "match_score": 0.85,
    "processing_time_ms": 2500
  }
}
```

### Key Log Messages

#### Business Events
- `API_CALL_SUCCESS` / `API_CALL_FAILED`: SAM.gov API interactions
- `OPPORTUNITY_PROCESSED` / `OPPORTUNITY_PROCESSING_FAILED`: Opportunity processing results
- `MATCH_FOUND` / `NO_MATCH_FOUND`: AI matching results
- `BEDROCK_CALL_SUCCESS` / `BEDROCK_CALL_FAILED`: Bedrock API interactions
- `BATCH_PROCESSING_COMPLETED` / `BATCH_PROCESSING_FAILED`: SQS batch processing

#### Performance Events
- `PERFORMANCE_*`: Operation timing metrics
- `METRIC_*`: Custom business metrics

### Correlation IDs

Each Lambda execution generates a unique correlation ID that tracks requests across all services and log entries. This enables:
- End-to-end request tracing
- Debugging complex workflows
- Performance analysis across service boundaries

## X-Ray Tracing

### Configuration

All Lambda functions are configured with:
```yaml
TracingConfig:
  Mode: Active
```

### Trace Annotations

Key annotations for filtering and analysis:
- `function_name`: Lambda function identifier
- `environment`: Deployment environment (dev/staging/prod)
- `opportunity_id`: Business entity identifier
- `match_score`: AI matching score
- `is_match`: Boolean match result
- `processing_stage`: Current processing phase
- `error_type`: Exception type for failed requests

### Trace Segments

Custom segments for major operations:
- `sam_api_processing`: SAM.gov API interactions
- `opportunity_processing`: Individual opportunity analysis
- `bedrock_extract_opportunity_info`: AI information extraction
- `bedrock_calculate_company_match`: AI matching analysis
- `sqs_batch_processing`: SQS message batch handling

## Custom CloudWatch Metrics

### Namespace
All custom metrics use the namespace: `AI-RFP-Response-Agent`

### Business Metrics

#### API Metrics
- `SuccessfulApiCalls`: Count of successful SAM.gov API calls
- `FailedApiCalls`: Count of failed SAM.gov API calls

#### Processing Metrics
- `OpportunitiesProcessed`: Count of successfully processed opportunities
- `OpportunityProcessingErrors`: Count of processing failures
- `ProcessingRate`: Opportunities processed per minute

#### AI/ML Metrics
- `MatchesFound`: Count of opportunities that match company capabilities
- `NoMatchesFound`: Count of opportunities that don't match
- `MatchScore`: Distribution of AI matching scores (0.0-1.0)
- `BedrockCallsSuccess`: Count of successful Bedrock API calls
- `BedrockCallsError`: Count of failed Bedrock API calls

#### System Metrics
- `ResourceUtilization`: Lambda memory/CPU utilization percentages

### Metric Dimensions

Metrics include relevant dimensions for filtering:
- `Service`: AWS service name (SAM.gov, Bedrock, etc.)
- `ModelId`: Bedrock model identifier
- `ResourceType`: Type of resource being monitored

## CloudWatch Alarms

### Critical Alarms

#### API Failure Rate
- **Metric**: `FailedApiCalls`
- **Threshold**: > 3 failures in 10 minutes
- **Action**: SNS notification to operations team

#### Opportunity Processing Failure
- **Metric**: `OpportunityProcessingErrors`
- **Threshold**: > 10 failures in 10 minutes
- **Action**: SNS notification to operations team

#### Low Match Rate
- **Metric**: `MatchesFound`
- **Threshold**: < 1 match in 2 hours
- **Action**: SNS notification (potential system issue)

#### Bedrock Error Rate
- **Metric**: `BedrockCallsError`
- **Threshold**: > 5 errors in 10 minutes
- **Action**: SNS notification to operations team

#### Processing Rate Drop
- **Metric**: `ProcessingRate`
- **Threshold**: < 0.5 opportunities/minute for 30 minutes
- **Action**: SNS notification (performance degradation)

### Lambda Function Alarms

#### Error Rate
- **Metric**: `AWS/Lambda Errors`
- **Threshold**: > 1 error per function
- **Action**: SNS notification

#### Duration
- **Metric**: `AWS/Lambda Duration`
- **Threshold**: Function-specific timeouts
- **Action**: SNS notification (performance issue)

#### Memory Usage
- **Metric**: `AWS/Lambda MemoryUtilization`
- **Threshold**: > 85% for 15 minutes
- **Action**: SNS notification (resource optimization needed)

### SQS Alarms

#### Dead Letter Queue
- **Metric**: `AWS/SQS ApproximateNumberOfVisibleMessages`
- **Queue**: Dead letter queue
- **Threshold**: > 0 messages
- **Action**: Immediate SNS notification

#### Queue Depth
- **Metric**: `AWS/SQS ApproximateNumberOfVisibleMessages`
- **Queue**: Main processing queue
- **Threshold**: > 100 messages for 15 minutes
- **Action**: SNS notification (backlog building)

### Cost Monitoring

#### Monthly Cost Alert
- **Metric**: `AWS/Billing EstimatedCharges`
- **Threshold**: > $100 USD
- **Action**: SNS notification to finance team

## CloudWatch Dashboard

### Dashboard Sections

#### 1. API Performance
- SAM.gov API success/failure rates
- API response times
- Daily download function metrics

#### 2. Processing Pipeline
- Opportunity processing rates
- Error rates by function
- SQS queue depths and throughput

#### 3. AI/ML Performance
- Match rates and score distributions
- Bedrock API performance
- Model-specific metrics

#### 4. System Health
- Lambda function performance
- Memory and CPU utilization
- Error rates across all functions

#### 5. Business Metrics
- Daily opportunity counts
- Match success rates
- Processing throughput trends

#### 6. Recent Errors
- Log queries showing recent errors
- Error patterns and trends
- Correlation ID tracking

## Log Aggregation and Search

### CloudWatch Logs Insights Queries

#### Recent Errors by Function
```sql
SOURCE '/aws/lambda/${BucketPrefix}-sam-gov-daily-download-dev' 
| fields @timestamp, correlation_id, message, context.error
| filter level = "ERROR"
| sort @timestamp desc
| limit 50
```

#### Match Score Distribution
```sql
SOURCE '/aws/lambda/${BucketPrefix}-sam-sqs-generate-match-reports-dev'
| fields @timestamp, context.match_score, context.is_match
| filter message = "MATCH_SCORE"
| stats avg(context.match_score), count() by bin(5m)
```

#### Processing Performance
```sql
SOURCE '/aws/lambda/${BucketPrefix}-sam-sqs-generate-match-reports-dev'
| fields @timestamp, context.processing_time_ms, context.opportunity_id
| filter message = "PERFORMANCE_opportunity_processing"
| stats avg(context.processing_time_ms), max(context.processing_time_ms) by bin(15m)
```

#### Correlation ID Tracing
```sql
fields @timestamp, @message, function_name
| filter correlation_id = "12345678-1234-1234-1234-123456789012"
| sort @timestamp asc
```

## Alerting Configuration

### SNS Topic
- **Topic Name**: `sam-alerts-{environment}`
- **Subscribers**: Operations team email addresses
- **Message Format**: JSON with alert details and context

### Alert Escalation
1. **Level 1**: Email notification to operations team
2. **Level 2**: Additional notification to management (for critical issues)
3. **Level 3**: Integration with incident management system (future enhancement)

## Monitoring Best Practices

### Development
1. Always use structured logging with correlation IDs
2. Add X-Ray annotations for business-relevant data
3. Publish custom metrics for business events
4. Use performance timers for critical operations

### Operations
1. Monitor dashboard daily for trends
2. Investigate alarms promptly
3. Use correlation IDs for debugging
4. Review cost metrics weekly

### Troubleshooting
1. Start with CloudWatch dashboard for overview
2. Use X-Ray traces for request flow analysis
3. Search logs with correlation IDs for detailed debugging
4. Check custom metrics for business impact assessment

## Future Enhancements

### Planned Improvements
1. **Machine Learning Anomaly Detection**: Use CloudWatch anomaly detection for automatic threshold adjustment
2. **Distributed Tracing**: Enhanced tracing across external API calls
3. **Real-time Alerting**: Integration with Slack/Teams for immediate notifications
4. **Predictive Monitoring**: ML-based prediction of system issues
5. **Cost Optimization**: Automated recommendations based on usage patterns

### Integration Opportunities
1. **AWS Config**: Configuration compliance monitoring
2. **AWS Security Hub**: Security event correlation
3. **AWS Systems Manager**: Automated remediation actions
4. **Third-party Tools**: Integration with external monitoring platforms

## Maintenance

### Regular Tasks
1. **Weekly**: Review dashboard trends and adjust thresholds
2. **Monthly**: Analyze cost metrics and optimize resources
3. **Quarterly**: Review and update alerting rules
4. **Annually**: Comprehensive monitoring strategy review

### Log Retention
- **CloudWatch Logs**: 30 days retention for all Lambda functions
- **X-Ray Traces**: 30 days retention (AWS default)
- **Custom Metrics**: 15 months retention (AWS default)

This monitoring system provides comprehensive visibility into the AI RFP Response Agent's performance, reliability, and business impact while enabling proactive issue detection and resolution.