## Generated with: 
## uvx --from diagrams python .\ai_rfp_agent.py
##
from diagrams import Diagram, Edge, Cluster
from diagrams.aws.compute import Lambda
from diagrams.aws.storage import S3
from diagrams.aws.database import RDS
from diagrams.aws.integration import SQS, Eventbridge
from diagrams.aws.management import CloudwatchEventTimeBased
from diagrams.aws.ml import Bedrock
from diagrams.aws.network import InternetGateway

with Diagram("AI Powered RFP Response Agent", 
             show=False, 
             direction="LR",
             graph_attr={"size": "20,12!", "dpi": "300", "nodesep": "1.3", "ranksep": "2.0"}):
    
    # Steps 1-4: Main pipeline

    sam_api = InternetGateway("SAM.GOV API")


    with Cluster("SAM Data Retrieval", 
            graph_attr={"margin": "30", "penwidth": "3", "style": "filled", "fillcolor": "lightblue"}):
        cron = CloudwatchEventTimeBased("Daily Cron")
        lambda_download = Lambda("sam-gov-daily-download")

    s3_data_in = S3("sam-data-in")
    s3_logs = S3("sam-download-files-logs")
    lambda_processor = Lambda("sam-json-processor")
    s3_extracted = S3("sam-extracted-json-resources")
    sqs_queue = SQS("sqs-sam-json-messages")
    lambda_match = Lambda("sam-sqs-generate-match-reports")
    
    # Step 6: BEDROCK AI MATCH PROCESSING
    with Cluster("BEDROCK AI MATCH PROCESSING", 
            graph_attr={"margin": "60", "penwidth": "3", "style": "filled", "fillcolor": "lightblue"}):
        bedrock_info = Bedrock("Get Opportunity Info")
        bedrock_match = Bedrock("Calculate Company Match")
        knowledge_base = RDS("Company Information KB")
    
    # Results Storage
    s3_matching_out = S3("sam-matching-out-sqs")
    
    # Step 7: Run Results
    with Cluster("Run Results",
            graph_attr={"margin": "60", "penwidth": "3", "style": "filled", "fillcolor": "lightblue"}):
        eventbridge = Eventbridge("sam-lambda-every-5min-summarizer")
        lambda_merge = Lambda("sam-merge-and-archive-result-logs")
    
    # Main flow


    sam_api >> lambda_download
    lambda_download >> sam_api
    cron >> lambda_download
    lambda_download >> s3_data_in >> lambda_processor >> s3_extracted >> sqs_queue >> lambda_match
    lambda_download >> s3_logs
    lambda_match >> sqs_queue
    lambda_match >> bedrock_info >> bedrock_match >> s3_matching_out
    knowledge_base >> bedrock_match >> knowledge_base
    eventbridge >> lambda_merge 
    s3_matching_out >> lambda_merge
    lambda_merge >> s3_matching_out