"""
Lambda function for sending email notifications with RTF attachments.
Triggered by S3 events when new response templates are created.
"""

import os
import json
import boto3
import logging
from datetime import datetime
from urllib.parse import unquote_plus
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import re
import csv
from io import StringIO

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Email Configuration
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "false").lower() in ['true', '1', 'yes', 'enabled']
SES_REGION = os.environ.get("SES_REGION", "us-east-1")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@example.com")
EMAIL_SUBJECT_TEMPLATE = os.environ.get("EMAIL_SUBJECT_TEMPLATE", "AWS AI-Powered RFI/RFP Response for {solicitation_number}")
EMAIL_BODY = os.environ.get("EMAIL_BODY", "Dear Team, here is the latest match for your review.")

# Subscription Configuration
SUBSCRIBERS_BUCKET = os.environ.get("SUBSCRIBERS_BUCKET", "sam-email-subscribers")
SUBSCRIBERS_FILE = os.environ.get("SUBSCRIBERS_FILE", "subscribers.csv")

# Initialize AWS clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses', region_name=SES_REGION)

def lambda_handler(event, context):
    """
    Lambda function triggered by S3 object creation.
    Sends email notifications with RTF file attachments for new response templates.
    """
    try:
        # Parse S3 event
        for record in event['Records']:
            # Get bucket and object key from the event
            source_bucket = record['s3']['bucket']['name']
            object_key = unquote_plus(record['s3']['object']['key'])
            
            logger.info(f"Processing file: {object_key} from bucket: {source_bucket}")
            
            # Only process RTF files that are response templates
            if not (object_key.lower().endswith('.rtf') and 'response_template' in object_key.lower()):
                logger.info(f"Skipping non-RTF response template file: {object_key}")
                continue
            
            # Extract solicitation number from filename or file content
            solicitation_number = extract_solicitation_number(object_key, source_bucket)
            
            # Check if email notifications are enabled
            if not EMAIL_ENABLED:
                logger.info(f"Email notifications are disabled (EMAIL_ENABLED=false). Skipping email for {object_key}")
                continue
            
            # Send email notification
            send_email_notification(source_bucket, object_key, solicitation_number)
            
            logger.info(f"Successfully sent email notification for {object_key}")
            
    except Exception as e:
        logger.error(f"Error processing Lambda event: {str(e)}")
        raise e
    
    return {
        'statusCode': 200,
        'body': json.dumps('Email notifications sent successfully')
    }

def extract_solicitation_number(object_key, bucket):
    """
    Extract solicitation number from filename or file content.
    First tries to extract from filename pattern, then from file content if needed.
    """
    try:
        # Method 1: Extract from filename pattern (prefix before '_response_template.rtf')
        filename = os.path.basename(object_key)
        if '_response_template.rtf' in filename.lower():
            solicitation_number = filename.split('_response_template.rtf')[0]
            logger.info(f"Extracted solicitation number from filename: {solicitation_number}")
            return solicitation_number
        
        # Method 2: Extract from file content if filename method fails
        try:
            response = s3_client.get_object(Bucket=bucket, Key=object_key)
            content = response['Body'].read().decode('utf-8', errors='ignore')
            
            # Look for solicitation number patterns in RTF content
            # Common patterns: "Solicitation: XXXXX" or "Solicitation Number: XXXXX"
            patterns = [
                r'Solicitation:\s*([A-Z0-9\-_]+)',
                r'Solicitation Number:\s*([A-Z0-9\-_]+)',
                r'Response to Solicitation\s+([A-Z0-9\-_]+)',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    solicitation_number = match.group(1)
                    logger.info(f"Extracted solicitation number from content: {solicitation_number}")
                    return solicitation_number
                    
        except Exception as e:
            logger.warning(f"Could not read file content to extract solicitation number: {str(e)}")
        
        # Method 3: Fallback - use filename without extension
        solicitation_number = os.path.splitext(filename)[0]
        logger.info(f"Using filename as fallback solicitation number: {solicitation_number}")
        return solicitation_number
        
    except Exception as e:
        logger.error(f"Error extracting solicitation number: {str(e)}")
        return "UNKNOWN"

def load_subscribers():
    """
    Load active subscribers from CSV file in S3.
    Expected CSV format: email,name,active,subscription_date
    Returns list of active subscriber email addresses.
    """
    try:
        response = s3_client.get_object(Bucket=SUBSCRIBERS_BUCKET, Key=SUBSCRIBERS_FILE)
        csv_content = response['Body'].read().decode('utf-8')
        
        subscribers = []
        csv_reader = csv.DictReader(StringIO(csv_content))
        
        for row in csv_reader:
            # Check if subscriber is active (case-insensitive)
            is_active = row.get('active', '').lower() in ['true', '1', 'yes', 'active']
            email = row.get('email', '').strip()
            
            if is_active and email:
                subscribers.append({
                    'email': email,
                    'name': row.get('name', '').strip(),
                    'subscription_date': row.get('subscription_date', '').strip()
                })
                
        logger.info(f"Loaded {len(subscribers)} active subscribers from {SUBSCRIBERS_BUCKET}/{SUBSCRIBERS_FILE}")
        return subscribers
        
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Subscribers file not found: {SUBSCRIBERS_BUCKET}/{SUBSCRIBERS_FILE}")
        return []
    except Exception as e:
        logger.error(f"Error loading subscribers: {str(e)}")
        return []

def send_email_notification(bucket, object_key, solicitation_number):
    """
    Send email notification with RTF file as attachment to all active subscribers.
    """
    try:
        # Load active subscribers
        subscribers = load_subscribers()
        if not subscribers:
            logger.warning("No active subscribers found, skipping email notification")
            return
            
        subscriber_emails = [sub['email'] for sub in subscribers]
        
        # Download the RTF file from S3
        response = s3_client.get_object(Bucket=bucket, Key=object_key)
        rtf_content = response['Body'].read()
        
        # Create email message
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = ', '.join(subscriber_emails)
        msg['Subject'] = EMAIL_SUBJECT_TEMPLATE.format(solicitation_number=solicitation_number)
        
        # Add body
        body = MIMEText(EMAIL_BODY, 'plain')
        msg.attach(body)
        
        # Add RTF attachment
        filename = os.path.basename(object_key)
        attachment = MIMEApplication(rtf_content)
        attachment.add_header('Content-Disposition', 'attachment', filename=filename)
        msg.attach(attachment)
        
        # Send email via SES
        ses_client.send_raw_email(
            Source=FROM_EMAIL,
            Destinations=subscriber_emails,
            RawMessage={'Data': msg.as_string()}
        )
        
        logger.info(f"Email sent successfully to {len(subscriber_emails)} subscribers with attachment {filename}")
        logger.info(f"Recipients: {', '.join(subscriber_emails)}")
        
    except Exception as e:
        logger.error(f"Error sending email notification: {str(e)}")
        raise e

def validate_ses_configuration():
    """
    Validate that SES is properly configured for sending emails.
    """
    try:
        # Check if sender email is verified
        response = ses_client.get_identity_verification_attributes(
            Identities=[FROM_EMAIL]
        )
        
        verification_status = response.get('VerificationAttributes', {}).get(FROM_EMAIL, {}).get('VerificationStatus')
        
        if verification_status != 'Success':
            logger.warning(f"FROM_EMAIL {FROM_EMAIL} is not verified in SES. Status: {verification_status}")
            return False
        
        logger.info(f"SES configuration validated successfully for {FROM_EMAIL}")
        return True
        
    except Exception as e:
        logger.error(f"Error validating SES configuration: {str(e)}")
        return False