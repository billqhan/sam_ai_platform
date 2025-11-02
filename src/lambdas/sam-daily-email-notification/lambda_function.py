"""
Lambda function for sending daily email notifications with website links and RTF attachments.
Triggered by EventBridge daily at 10am EST.
Sends summary of the most recent day's processed opportunities.
"""

import os
import json
import boto3
import logging
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import csv
from io import StringIO, BytesIO
import zipfile

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Email Configuration
EMAIL_ENABLED = os.environ.get("EMAIL_ENABLED", "true").lower() in ['true', '1', 'yes', 'enabled']
SES_REGION = os.environ.get("SES_REGION", "us-east-1")
FROM_EMAIL = os.environ.get("FROM_EMAIL", "noreply@example.com")
EMAIL_SUBJECT_TEMPLATE = os.environ.get("EMAIL_SUBJECT_TEMPLATE", "Daily AWS AI-Powered RFI/RFP Response for {date}")
EMAIL_BODY_TEMPLATE = os.environ.get("EMAIL_BODY_TEMPLATE", 
    "Dear Team, here is the Daily Website for your review.\n\n"
    "I have attached a zip file containing only the high scoring opportunity matches for {date}.\n\n"
    "Please review the Daily Opportunities Website at the URL below for a summary of all data that was processed.")

# S3 Configuration
OPPORTUNITY_RESPONSES_BUCKET = os.environ.get("OPPORTUNITY_RESPONSES_BUCKET", "ktest-sam-opportunity-responses-dev")
WEBSITE_BUCKET = os.environ.get("WEBSITE_BUCKET", "ktest-sam-website-dev")
WEBSITE_BASE_URL = os.environ.get("WEBSITE_BASE_URL", "http://ktest-sam-website-dev.s3-website-us-east-1.amazonaws.com")

# Subscription Configuration
SUBSCRIBERS_BUCKET = os.environ.get("SUBSCRIBERS_BUCKET", "ktest-sam-subscribers")
SUBSCRIBERS_FILE = os.environ.get("SUBSCRIBERS_FILE", "subscribers_daily.csv")

# Attachment Configuration
ATTACHMENT_TYPE = os.environ.get("ATTACHMENT_TYPE", "txt").lower()

# Initialize AWS clients
s3_client = boto3.client('s3')
ses_client = boto3.client('ses', region_name=SES_REGION)

def lambda_handler(event, context):
    """
    Lambda function triggered by EventBridge daily schedule.
    Sends daily email notifications with website links and RTF attachments.
    """
    try:
        logger.info("Starting daily email notification process")
        
        # Check if email notifications are enabled
        if not EMAIL_ENABLED:
            logger.info("Email notifications are disabled (EMAIL_ENABLED=false). Exiting.")
            return {
                'statusCode': 200,
                'body': json.dumps('Email notifications disabled')
            }
        
        # Find the most recent date with processed data
        most_recent_date = find_most_recent_processed_date()
        if not most_recent_date:
            logger.warning("No processed data found. Skipping email notification.")
            return {
                'statusCode': 200,
                'body': json.dumps('No processed data found')
            }
        
        logger.info(f"Most recent processed date: {most_recent_date}")
        
        # Generate website URL for the most recent date
        website_url = generate_website_url(most_recent_date)
        
        # Create zip file with attachment matches for the most recent date
        zip_content = create_attachment_zip(most_recent_date)
        
        # Send email notification
        send_daily_email_notification(most_recent_date, website_url, zip_content)
        
        logger.info("Daily email notification process completed successfully")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Daily email notifications sent successfully',
                'date': most_recent_date,
                'website_url': website_url
            })
        }
        
    except Exception as e:
        logger.error(f"Error in daily email notification process: {str(e)}")
        raise e

def find_most_recent_processed_date():
    """
    Find the most recent date with processed opportunity data in S3.
    Returns date in YYYY-MM-DD format.
    """
    try:
        # List objects in the opportunity responses bucket to find date folders
        response = s3_client.list_objects_v2(
            Bucket=OPPORTUNITY_RESPONSES_BUCKET,
            Delimiter='/'
        )
        
        date_folders = []
        if 'CommonPrefixes' in response:
            for prefix in response['CommonPrefixes']:
                folder_name = prefix['Prefix'].rstrip('/')
                # Check if folder name matches YYYY-MM-DD pattern
                try:
                    datetime.strptime(folder_name, '%Y-%m-%d')
                    date_folders.append(folder_name)
                except ValueError:
                    continue
        
        if not date_folders:
            logger.warning("No date folders found in opportunity responses bucket")
            return None
        
        # Sort dates and return the most recent
        date_folders.sort(reverse=True)
        most_recent = date_folders[0]
        
        # Verify that this date has matches folder with attachment files
        matches_prefix = f"{most_recent}/matches/"
        matches_response = s3_client.list_objects_v2(
            Bucket=OPPORTUNITY_RESPONSES_BUCKET,
            Prefix=matches_prefix,
            MaxKeys=1
        )
        
        if 'Contents' not in matches_response:
            logger.warning(f"No matches found for date {most_recent}")
            # Try the next most recent date
            if len(date_folders) > 1:
                return date_folders[1]
            return None
        
        return most_recent
        
    except Exception as e:
        logger.error(f"Error finding most recent processed date: {str(e)}")
        return None

def generate_website_url(date_str):
    """
    Generate the website URL for the daily summary page.
    Converts YYYY-MM-DD to YYYYMMDD format for URL.
    """
    try:
        # Convert YYYY-MM-DD to YYYYMMDD
        date_obj = datetime.strptime(date_str, '%Y-%m-%d')
        date_formatted = date_obj.strftime('%Y%m%d')
        
        website_url = f"{WEBSITE_BASE_URL}/dashboards/Summary_{date_formatted}.html"
        logger.info(f"Generated website URL: {website_url}")
        
        return website_url
        
    except Exception as e:
        logger.error(f"Error generating website URL: {str(e)}")
        return f"{WEBSITE_BASE_URL}/dashboards/"

def create_attachment_zip(date_str):
    """
    Create a zip file containing all attachment files from the matches folder for the given date.
    File type is determined by ATTACHMENT_TYPE environment variable (rtf or txt).
    Returns zip file content as bytes.
    """
    try:
        matches_prefix = f"{date_str}/matches/"
        
        # Validate attachment type
        if ATTACHMENT_TYPE not in ['rtf', 'txt']:
            logger.error(f"Invalid ATTACHMENT_TYPE: {ATTACHMENT_TYPE}. Must be 'rtf' or 'txt'")
            return None
        
        # List all files in the matches folder
        response = s3_client.list_objects_v2(
            Bucket=OPPORTUNITY_RESPONSES_BUCKET,
            Prefix=matches_prefix
        )
        
        if 'Contents' not in response:
            logger.warning(f"No files found in matches folder for date {date_str}")
            return None
        
        # Filter files by attachment type
        file_extension = f".{ATTACHMENT_TYPE}"
        attachment_files = [obj for obj in response['Contents'] if obj['Key'].lower().endswith(file_extension)]
        
        if not attachment_files:
            logger.warning(f"No {ATTACHMENT_TYPE.upper()} files found in matches folder for date {date_str}")
            return None
        
        logger.info(f"Found {len(attachment_files)} {ATTACHMENT_TYPE.upper()} files for date {date_str}")
        
        # Create zip file in memory
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for file_obj in attachment_files:
                try:
                    # Download file from S3
                    file_response = s3_client.get_object(
                        Bucket=OPPORTUNITY_RESPONSES_BUCKET,
                        Key=file_obj['Key']
                    )
                    file_content = file_response['Body'].read()
                    
                    # Add to zip with just the filename (not full path)
                    filename = os.path.basename(file_obj['Key'])
                    zip_file.writestr(filename, file_content)
                    
                except Exception as e:
                    logger.error(f"Error adding {file_obj['Key']} to zip: {str(e)}")
                    continue
        
        zip_content = zip_buffer.getvalue()
        logger.info(f"Created zip file with {len(attachment_files)} {ATTACHMENT_TYPE.upper()} files, size: {len(zip_content)} bytes")
        
        return zip_content
        
    except Exception as e:
        logger.error(f"Error creating {ATTACHMENT_TYPE.upper()} zip file: {str(e)}")
        return None

def load_daily_subscribers():
    """
    Load active daily subscribers from CSV file in S3.
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
                
        logger.info(f"Loaded {len(subscribers)} active daily subscribers from {SUBSCRIBERS_BUCKET}/{SUBSCRIBERS_FILE}")
        return subscribers
        
    except s3_client.exceptions.NoSuchKey:
        logger.warning(f"Daily subscribers file not found: {SUBSCRIBERS_BUCKET}/{SUBSCRIBERS_FILE}")
        return []
    except Exception as e:
        logger.error(f"Error loading daily subscribers: {str(e)}")
        return []

def send_daily_email_notification(date_str, website_url, zip_content):
    """
    Send personalized daily email notifications with website link and attachment zip file.
    Sends individual emails to each subscriber with their name personalized.
    """
    try:
        # Load active daily subscribers
        subscribers = load_daily_subscribers()
        if not subscribers:
            logger.warning("No active daily subscribers found, skipping email notification")
            return
        
        successful_sends = 0
        failed_sends = 0
        
        # Send individual personalized emails to each subscriber
        for subscriber in subscribers:
            try:
                email = subscriber['email']
                name = subscriber.get('name', 'Team Member')  # Default to 'Team Member' if no name
                
                # Create personalized email message
                msg = MIMEMultipart()
                msg['From'] = FROM_EMAIL
                msg['To'] = email
                msg['Subject'] = EMAIL_SUBJECT_TEMPLATE.format(date=date_str)
                
                # Create personalized email body with website link
                # Convert \n escape sequences to actual newlines and replace {name} with actual name
                email_body = EMAIL_BODY_TEMPLATE.replace('\\n', '\n').format(date=date_str, name=name)
                email_body += f"\n\nDaily Opportunities Website: {website_url}"
                
                body = MIMEText(email_body, 'plain')
                msg.attach(body)
                
                # Add zip attachment if available
                if zip_content:
                    zip_filename = f"high_scoring_matches_{ATTACHMENT_TYPE}_{date_str.replace('-', '')}.zip"
                    attachment = MIMEApplication(zip_content)
                    attachment.add_header('Content-Disposition', 'attachment', filename=zip_filename)
                    msg.attach(attachment)
                
                # Send individual email via SES
                ses_client.send_raw_email(
                    Source=FROM_EMAIL,
                    Destinations=[email],
                    RawMessage={'Data': msg.as_string()}
                )
                
                successful_sends += 1
                logger.info(f"Email sent successfully to {email} (Name: {name})")
                
            except Exception as e:
                failed_sends += 1
                logger.error(f"Failed to send email to {subscriber.get('email', 'unknown')}: {str(e)}")
                continue
        
        # Log summary
        total_subscribers = len(subscribers)
        logger.info(f"Daily email notification summary:")
        logger.info(f"  Total subscribers: {total_subscribers}")
        logger.info(f"  Successful sends: {successful_sends}")
        logger.info(f"  Failed sends: {failed_sends}")
        logger.info(f"  Subject: {EMAIL_SUBJECT_TEMPLATE.format(date=date_str)}")
        
        if zip_content:
            zip_filename = f"high_scoring_matches_{ATTACHMENT_TYPE}_{date_str.replace('-', '')}.zip"
            logger.info(f"  Attachment: {zip_filename} (Type: {ATTACHMENT_TYPE.upper()})")
        
        if failed_sends > 0:
            logger.warning(f"Some emails failed to send. Check logs for details.")
        
    except Exception as e:
        logger.error(f"Error in daily email notification process: {str(e)}")
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