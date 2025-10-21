# Sam Merge and Archive Lambda Stray Files Fix Session Report

**Date:** October 21, 2025  
**Issue:** Stray files left in s3://ktest-sam-matching-out-runs-dev/runs/raw/ not being processed by sam-merge-and-archive-results-logs lambda function  
**Status:** ✅ RESOLVED

## Problem Summary

The user reported that stray files were accumulating in the S3 bucket `s3://ktest-sam-matching-out-runs-dev/runs/raw/` and were not being processed by the `sam-merge-and-archive-results-logs` lambda function that should run every 5 minutes via EventBridge.

## Investigation Findings

### Root Cause Analysis

1. **Lambda Function Import Error**: The lambda function was failing with `Runtime.ImportModuleError: Unable to import module 'lambda_function': No module named 'lambda_function'`

2. **Missing Handler File**: The CloudFormation template was configured to use `lambda_function.lambda_handler` as the handler, but the deployment was missing the `handler.py` file that contains the actual implementation.

3. **Deployment Issue**: The lambda function code was not properly packaged and deployed, causing it to fail on every invocation.

### Evidence from CloudWatch Logs

```
[ERROR] Runtime.ImportModuleError: Unable to import module 'lambda_function': No module named 'lambda_function'
Traceback (most recent call last):
```

### Stray Files Found

10 files were found in the raw directory, dating from around 09:02-09:03 UTC (several hours old):
- `20251021t1302Z_DARPA-PS-25-32.json`
- `20251021t1302Z_DARPA-SN-25-107.json`
- `20251021t1302Z_DARPA-SN-25-85.json`
- And 7 more files...

## Solution Implementation

### 1. Lambda Function Code Fix

**File Modified:** `src/lambdas/sam-merge-and-archive-result-logs/handler.py`

**Key Changes:**
- Enhanced logic to process both current 5-minute window files AND older missed files
- Added better error handling and logging
- Added tracking for old files processed

**Before:**
```python
if not (bucket_start <= last_mod < bucket_end):
    continue
```

**After:**
```python
# Process files from current 5-minute bucket OR older files that were never processed
in_current_bucket = bucket_start <= last_mod < bucket_end
is_old_file = last_mod < bucket_start

if in_current_bucket or is_old_file:
    # Process the file...
    if is_old_file:
        old_files_processed += 1
```

### 2. Lambda Function Deployment

**Action:** Redeployed the lambda function with correct code packaging
```powershell
aws lambda update-function-code --function-name "ktest-sam-merge-and-archive-result-logs-dev" --zip-file "fileb://$zipFile"
```

**Result:** Function successfully updated and working

### 3. Verification Steps

1. **Function Test**: Manual invocation processed all 10 stray files
2. **S3 Verification**: Raw directory emptied, files moved to archive
3. **Summary File**: Created `20251021T1400Z.json` with aggregated data
4. **EventBridge Rule**: Confirmed enabled and running every 5 minutes

## Results

### ✅ Immediate Fixes
- **All 10 stray files processed and archived**
- **Lambda function now working correctly**
- **EventBridge schedule active (every 5 minutes)**
- **Summary file created with aggregated data**

### ✅ Test Results
```json
{
  "processed": 10,
  "archived": 10, 
  "old_files_processed": 10,
  "summary_key": "runs/20251021T1400Z.json"
}
```

### ✅ S3 State After Fix
- **Raw directory**: Empty (all files processed)
- **Archive directory**: Contains all 10 processed files
- **Summary file**: `20251021T1400Z.json` (284,575 bytes)

### ✅ EventBridge Configuration
```json
{
  "Name": "sam-lambda-every-5min-summarizer-dev",
  "ScheduleExpression": "rate(5 minutes)",
  "State": "ENABLED",
  "Description": "Trigger merge and archive Lambda function every 5 minutes"
}
```

## Technical Details

### Lambda Function Configuration
- **Function Name**: `ktest-sam-merge-and-archive-result-logs-dev`
- **Runtime**: Python 3.11
- **Handler**: `lambda_function.lambda_handler`
- **Memory**: 128 MB
- **Timeout**: 300 seconds (5 minutes)
- **Environment Variables**:
  - `S3_OUT_BUCKET`: `ktest-sam-matching-out-runs-dev`
  - `active`: `true`

### File Processing Logic
1. **Current Window Processing**: Files modified in the last 5-minute bucket
2. **Backlog Processing**: Older files that were never processed due to previous failures
3. **Archival**: Files moved from `runs/raw/` to `runs/archive/`
4. **Aggregation**: Summary JSON file created with all processed records

## Prevention Measures

### Enhanced Error Handling
- Added JSON parsing error logging
- Better tracking of old vs. new file processing
- Improved return values with detailed metrics

### Monitoring Improvements
- Function now logs when old files are processed
- Clear distinction between current and backlog processing
- Detailed error messages for troubleshooting

## Files Modified

| File | Type | Changes |
|------|------|---------|
| `src/lambdas/sam-merge-and-archive-result-logs/handler.py` | Code | Enhanced processing logic, error handling |

## Git Commit

```
commit adb0f26
Fix sam-merge-and-archive-result-logs lambda function

- Fixed Runtime.ImportModuleError by ensuring handler.py is included in deployment
- Enhanced logic to process both current 5-minute window files AND older missed files
- Added better error handling and logging for old file processing
- Successfully processed and archived 10 stray files from s3://ktest-sam-matching-out-runs-dev/runs/raw/
- Lambda function now working correctly with EventBridge 5-minute schedule
```

## Conclusion

The issue has been completely resolved. The lambda function is now working correctly and will:
1. Process new files every 5 minutes as intended
2. Handle any future backlog of missed files
3. Properly archive processed files
4. Create summary files for downstream processing

The system is now functioning as designed and will prevent future accumulation of stray files in the raw directory.