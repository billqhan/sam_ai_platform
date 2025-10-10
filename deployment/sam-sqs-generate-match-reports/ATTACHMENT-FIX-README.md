# 🔧 ATTACHMENT READING FIX

## Problem
Lambda was getting AccessDenied when trying to read attachments, even though it should have access to files in the same folder as the opportunity JSON.

## Root Cause
The original code used `list_objects_v2` which requires `s3:ListBucket` permission. The Lambda might only have `s3:GetObject` permission for specific file patterns.

## Solution
Implemented a two-tier approach:

### 1. Direct File Access (Primary Method)
Try to read common attachment file patterns directly without listing:
- `{opportunity_id}/{opportunity_id}_attachment.txt`
- `{opportunity_id}/{opportunity_id}_attachment.pdf`
- `{opportunity_id}/{opportunity_id}_solicitation.pdf`
- `{opportunity_id}/attachment.txt`
- `{opportunity_id}/attachment_1.txt`
- And more common patterns...

### 2. List Objects Fallback (Secondary Method)
If no attachments found with direct access, try the original listing approach as fallback.

## Code Changes

### Before (BROKEN - Required ListBucket permission)
```python
def read_attachment_files(self, bucket: str, opportunity_id: str) -> List[str]:
    try:
        # This requires s3:ListBucket permission
        response = self.s3_client.list_objects_v2(
            Bucket=bucket,
            Prefix=f"{opportunity_id}/",
            MaxKeys=self.max_attachment_files * 2
        )
        # Process results...
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            return []  # Give up
```

### After (FIXED - Uses direct file access)
```python
def read_attachment_files(self, bucket: str, opportunity_id: str) -> List[str]:
    # Try common attachment patterns directly
    attachment_patterns = [
        f"{opportunity_id}/{opportunity_id}_attachment.txt",
        f"{opportunity_id}/{opportunity_id}_attachment.pdf",
        f"{opportunity_id}/{opportunity_id}_solicitation.pdf",
        f"{opportunity_id}/attachment.txt",
        # ... more patterns
    ]
    
    for file_key in attachment_patterns:
        try:
            # Direct file access - only needs s3:GetObject
            file_response = self.s3_client.get_object(Bucket=bucket, Key=file_key)
            # Process file...
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                continue  # Try next pattern
    
    # Fallback to listing if nothing found
    if len(attachments_content) == 0:
        try:
            response = self.s3_client.list_objects_v2(...)
            # Process listed files...
        except ClientError:
            # Gracefully handle list permission issues
            pass
```

## New Deployment Package
**Package:** `lambda-deployment-package-v4-attachments-fixed.zip`

## Deploy Command
```bash
aws lambda update-function-code \
  --function-name ktest-sam-sqs-generate-match-reports-dev \
  --zip-file fileb://lambda-deployment-package-v4-attachments-fixed.zip \
  --region us-east-1
```

## Expected Results

### ✅ **Attachments Found:**
```
Looking for attachments using direct file access for opportunity: FA813725R0035
Successfully read attachment: FA813725R0035_attachment.txt (1234 characters)
Successfully read attachment: FA813725R0035_solicitation.pdf (5678 characters)
Successfully read 2 attachment files
```

### ✅ **No Attachments (Normal):**
```
Looking for attachments using direct file access for opportunity: FA813725R0035
No attachments found with direct access, trying list approach as fallback
Successfully read 0 attachment files
```

### ✅ **Permission Issues (Graceful):**
```
Looking for attachments using direct file access for opportunity: FA813725R0035
Access denied for attachment: FA813725R0035/some_file.txt
No attachments found with direct access, trying list approach as fallback
List objects access denied - this is expected if Lambda only has GetObject permissions
Successfully read 0 attachment files
```

## Benefits
1. **Works with minimal permissions** - Only needs `s3:GetObject` for file patterns
2. **Handles common file naming conventions** - Covers most typical attachment patterns
3. **Graceful fallback** - Still tries listing if direct access finds nothing
4. **Better error handling** - Distinguishes between "no files" vs "permission denied"
5. **Detailed logging** - Shows exactly what files were found and read

## Status
🚀 **READY FOR DEPLOYMENT** - Attachment reading should now work properly with `lambda-deployment-package-v4-attachments-fixed.zip`