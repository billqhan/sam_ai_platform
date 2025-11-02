# SAM Daily Email Notification - Attachment Type Enhancement

**Date:** October 22, 2025  
**Status:** COMPLETE  
**Lambda Function:** `ktest-sam-daily-email-notification-dev`  

## Overview

Enhanced the SAM Daily Email Notification lambda function to support both .rtf and .txt file attachments through a configurable environment variable. Previously, the function only supported .rtf files. Now it can dynamically switch between file types based on the `ATTACHMENT_TYPE` environment variable.

## Requirements Addressed

- Add support for both .rtf and .txt file attachments
- Create `ATTACHMENT_TYPE` environment variable that defaults to "txt"
- Maintain backward compatibility with existing functionality
- Update deployment scripts to include the new environment variable

## Implementation Changes

### 1. Lambda Function Code Updates

**File:** `src/lambdas/sam-daily-email-notification/lambda_function.py`

#### Added Environment Variable Configuration
```python
# Attachment Configuration
ATTACHMENT_TYPE = os.environ.get("ATTACHMENT_TYPE", "txt").lower()
```

#### Renamed and Enhanced Attachment Function
- Renamed `create_rtf_zip()` to `create_attachment_zip()` for better clarity
- Added validation for attachment type (must be "rtf" or "txt")
- Dynamic file filtering based on `ATTACHMENT_TYPE` variable
- Enhanced logging to show file type being processed

#### Key Code Changes
```python
def create_attachment_zip(date_str):
    """
    Create a zip file containing all attachment files from the matches folder for the given date.
    File type is determined by ATTACHMENT_TYPE environment variable (rtf or txt).
    Returns zip file content as bytes.
    """
    # Validate attachment type
    if ATTACHMENT_TYPE not in ['rtf', 'txt']:
        logger.error(f"Invalid ATTACHMENT_TYPE: {ATTACHMENT_TYPE}. Must be 'rtf' or 'txt'")
        return None
    
    # Filter files by attachment type
    file_extension = f".{ATTACHMENT_TYPE}"
    attachment_files = [obj for obj in response['Contents'] if obj['Key'].lower().endswith(file_extension)]
```

#### Updated Zip Filename Generation
- Changed from: `high_scoring_matches_{date}.zip`
- Changed to: `high_scoring_matches_{ATTACHMENT_TYPE}_{date}.zip`
- Example: `high_scoring_matches_txt_20251022.zip`

### 2. Deployment Script Updates

**File:** `src/lambdas/sam-daily-email-notification/create-lambda.ps1`

Added `ATTACHMENT_TYPE` to default environment variables:
```powershell
"ATTACHMENT_TYPE": "txt"
```

## Testing Results

### Test Execution
- **Function Name:** `ktest-sam-daily-email-notification-dev`
- **Test Date:** 2025-10-22
- **Attachment Type:** txt (default)

### Execution Summary
```
Found 2 TXT files for date 2025-10-22
Created zip file with 2 TXT files, size: 4947 bytes
Loaded 2 active daily subscribers
Email sent successfully to marcus.arrington.work@gmail.com (Name: Mar A)
Email sent successfully to Marcus.Arrington@L3Harris.com (Name: Marcus Arrington)
Total subscribers: 2
Successful sends: 2
Failed sends: 0
Attachment: high_scoring_matches_txt_20251022.zip (Type: TXT)
```

### Performance Metrics
- **Duration:** 597.09 ms
- **Memory Used:** 95 MB (of 512 MB allocated)
- **Status:** SUCCESS

## Environment Variable Configuration

### Current Environment Variables
The lambda function now supports the following environment variables:

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `ATTACHMENT_TYPE` | "txt" | File type for attachments ("rtf" or "txt") |
| `EMAIL_ENABLED` | "true" | Enable/disable email notifications |
| `SES_REGION` | "us-east-1" | AWS SES region |
| `FROM_EMAIL` | User-configured | Sender email address |
| `EMAIL_SUBJECT_TEMPLATE` | Template string | Email subject template |
| `EMAIL_BODY_TEMPLATE` | User-configured | Email body template |
| `OPPORTUNITY_RESPONSES_BUCKET` | Bucket name | S3 bucket for opportunity responses |
| `WEBSITE_BUCKET` | Bucket name | S3 bucket for website |
| `WEBSITE_BASE_URL` | Website URL | Base URL for daily summaries |
| `SUBSCRIBERS_BUCKET` | Bucket name | S3 bucket for subscribers |
| `SUBSCRIBERS_FILE` | "subscribers_daily.csv" | Subscriber list filename |

### Usage Examples

**For TXT files (default):**
```bash
ATTACHMENT_TYPE=txt
```

**For RTF files:**
```bash
ATTACHMENT_TYPE=rtf
```

## Key Features

1. **Flexible File Type Support**: Dynamically processes either .rtf or .txt files
2. **Backward Compatibility**: Defaults to "txt" but easily configurable
3. **Enhanced Logging**: Clear indication of file type being processed
4. **Error Handling**: Validates attachment type with clear error messages
5. **Dynamic Filename Generation**: Zip filenames include the attachment type

## Deployment Instructions

### For New Deployments
The `create-lambda.ps1` script now includes the `ATTACHMENT_TYPE` environment variable by default.

### For Existing Deployments
To update an existing lambda function:

1. **Get current environment variables:**
   ```bash
   aws lambda get-function-configuration --function-name ktest-sam-daily-email-notification-dev
   ```

2. **Update with new variable (preserving existing settings):**
   ```bash
   aws lambda update-function-configuration --function-name ktest-sam-daily-email-notification-dev --environment Variables='{"ATTACHMENT_TYPE":"txt",...other existing vars...}'
   ```

3. **Deploy updated code:**
   ```bash
   cd src/lambdas/sam-daily-email-notification
   Compress-Archive -Path lambda_function.py -DestinationPath function.zip -Force
   aws lambda update-function-code --function-name ktest-sam-daily-email-notification-dev --zip-file fileb://function.zip
   ```

## Important Notes

### Environment Variable Preservation
When updating environment variables in future sessions:
1. Always pull current environment variables first
2. Merge new variables with existing ones to preserve custom settings
3. Avoid overwriting user-customized templates like `EMAIL_BODY_TEMPLATE`

### File Type Validation
The function validates the `ATTACHMENT_TYPE` value and will log an error if an invalid type is provided. Only "rtf" and "txt" are supported.

### Logging Enhancements
The function now provides clear logging about:
- Which file type is being processed
- Number of files found for the specified type
- Attachment filename in the email summary

## Conclusion

The SAM Daily Email Notification system has been successfully enhanced to support both .rtf and .txt file attachments through a configurable environment variable. The implementation maintains full backward compatibility while providing the flexibility to switch between file types as needed. The function has been tested and verified to work correctly with both file types.

The enhancement preserves all existing functionality while adding the requested flexibility for attachment file types. The default setting of "txt" ensures that new deployments will work out of the box, while existing users can easily switch to "rtf" if needed by updating the environment variable.