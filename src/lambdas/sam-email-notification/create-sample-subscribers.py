#!/usr/bin/env python3
"""
Utility script to create and upload a sample subscribers CSV file to S3.
Usage: python create-sample-subscribers.py --bucket your-bucket --file subscribers.csv
"""

import boto3
import csv
import argparse
from datetime import datetime

def create_sample_csv():
    """Create sample CSV content"""
    sample_data = [
        {
            'email': 'team@yourcompany.com',
            'name': 'Team Lead',
            'active': 'true',
            'subscription_date': '2024-01-15'
        },
        {
            'email': 'manager@yourcompany.com', 
            'name': 'Project Manager',
            'active': 'true',
            'subscription_date': '2024-01-20'
        },
        {
            'email': 'analyst@yourcompany.com',
            'name': 'Business Analyst', 
            'active': 'true',
            'subscription_date': '2024-01-25'
        }
    ]
    
    # Create CSV content
    csv_content = "email,name,active,subscription_date\n"
    for row in sample_data:
        csv_content += f"{row['email']},{row['name']},{row['active']},{row['subscription_date']}\n"
    
    return csv_content

def upload_to_s3(bucket, key, content):
    """Upload CSV content to S3"""
    s3_client = boto3.client('s3')
    
    try:
        s3_client.put_object(
            Bucket=bucket,
            Key=key,
            Body=content.encode('utf-8'),
            ContentType='text/csv'
        )
        print(f"Successfully uploaded subscribers file to s3://{bucket}/{key}")
        return True
    except Exception as e:
        print(f"Error uploading to S3: {str(e)}")
        return False

def main():
    parser = argparse.ArgumentParser(description='Create and upload sample subscribers CSV')
    parser.add_argument('--bucket', required=True, help='S3 bucket name')
    parser.add_argument('--file', default='subscribers.csv', help='CSV filename (default: subscribers.csv)')
    parser.add_argument('--local-only', action='store_true', help='Only create local file, do not upload to S3')
    
    args = parser.parse_args()
    
    # Create CSV content
    csv_content = create_sample_csv()
    
    # Save locally
    with open(args.file, 'w') as f:
        f.write(csv_content)
    print(f"Created local file: {args.file}")
    
    # Upload to S3 if requested
    if not args.local_only:
        upload_to_s3(args.bucket, args.file, csv_content)

if __name__ == '__main__':
    main()