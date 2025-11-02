import os
import boto3
import json
from datetime import datetime, timedelta, timezone

s3 = boto3.client("s3")

S3_BUCKET = os.environ['S3_OUT_BUCKET']
ACTIVE = os.environ.get("active", "false").lower() == "true"

def get_last_complete_bucket(now=None, size_minutes=5):
    if not now:
        now = datetime.now(timezone.utc)
    # Truncate to previous full interval: e.g., 11:44 => 11:40
    bucket_end = now.replace(second=0, microsecond=0)
    minute_mod = bucket_end.minute % size_minutes
    # Always snap to last bucket_edge BEFORE now (never in future)
    bucket_end = bucket_end - timedelta(minutes=minute_mod)
    bucket_start = bucket_end - timedelta(minutes=size_minutes)
    return bucket_start, bucket_end


def list_s3_keys(prefix):
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=prefix):
        for obj in page.get("Contents", []):
            yield obj['Key']

def lambda_handler(event, context):
    if not ACTIVE:
        print("Merger Lambda not active.")
        return {"status": "inactive"}
    
    now = datetime.now(timezone.utc)
    bucket_start, bucket_end = get_last_complete_bucket(now, size_minutes=5)
    file_str = bucket_end.strftime("%Y%m%dT%H%M")
    summary_key = f"runs/{file_str}Z.json"
    
    raw_prefix = "runs/raw/"
    archive_prefix = "runs/archive/"
    summary = []
    to_archive = []
    old_files_processed = 0
    
    for key in list_s3_keys(raw_prefix):
        obj = s3.head_object(Bucket=S3_BUCKET, Key=key)
        last_mod = obj['LastModified']
        
        # Process files from current 5-minute bucket OR older files that were never processed
        in_current_bucket = bucket_start <= last_mod < bucket_end
        is_old_file = last_mod < bucket_start
        
        if in_current_bucket or is_old_file:
            # Load and add to summary
            body = s3.get_object(Bucket=S3_BUCKET, Key=key)['Body'].read()
            try:
                record = json.loads(body)
                summary.append(record)
                to_archive.append(key)
                if is_old_file:
                    old_files_processed += 1
            except Exception as e:
                print(f"Failed to parse JSON for {key}: {e}")
                continue
    
    if summary:
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=summary_key,
            Body=json.dumps(summary, indent=2).encode('utf-8')
        )
        print(f"Wrote {len(summary)} records to {summary_key}")
        if old_files_processed > 0:
            print(f"Processed {old_files_processed} old files that were previously missed")
        
        # Move to archive after merging
        for key in to_archive:
            archive_key = archive_prefix + os.path.basename(key)
            s3.copy_object(Bucket=S3_BUCKET, CopySource={'Bucket': S3_BUCKET, 'Key': key}, Key=archive_key)
            s3.delete_object(Bucket=S3_BUCKET, Key=key)
        print(f"Archived {len(to_archive)} files.")
    else:
        print(f"No new records found for this interval {bucket_start} to {bucket_end} .")

    return {
        "processed": len(summary), 
        "archived": len(to_archive), 
        "old_files_processed": old_files_processed,
        "summary_key": summary_key
    }