# Task 3: Opportunity Processing Testing - Troubleshooting Session

## Session Overview
**Date**: October 8, 2025  
**Task**: Testing and fixing the SAM.gov opportunity processing Lambda function  
**Status**: ✅ **COMPLETED SUCCESSFULLY**

## Initial State
- SAM.gov data download (Task 2) was working successfully
- 178 opportunities downloaded to `ktest-sam-data-in-dev` bucket
- Ready to test opportunity processing (Task 6.2)

## Issues Encountered and Solutions

### Issue 1: Python Cache Files (.pyc)
**Problem**: Multiple .pyc files created in `src/shared/__pycache__/` directory
**Solution**: 
- Cleaned up existing .pyc files using `Remove-Item -Recurse -Force`
- Created comprehensive `.gitignore` file to prevent future cache file commits
- Added patterns for Python, PyTest, virtual environments, IDE files, and AWS-specific files

### Issue 2: AWS CLI Pagination (`--more--` prompts)
**Problem**: AWS CLI commands showing `--more--` prompts requiring spacebar input
**Solutions Applied**:
1. **Immediate fix**: `$env:AWS_PAGER = ""`
2. **Permanent fix**: Added to PowerShell profile
3. **Alternative options**: `--no-paginate` flag or `Out-String` piping

### Issue 3: Lambda Function Import Errors
**Problem**: `Runtime.ImportModuleError: No module named 'lambda_function'`
**Root Cause**: CloudFormation expected `lambda_function.py` but code was in `handler.py`
**Solution**: 
- Renamed `handler.py` to `lambda_function.py` 
- Updated Lambda function code using deployment script

### Issue 4: Missing Dependencies (aiohttp)
**Problem**: `No module named 'aiohttp'` error
**Root Cause**: Dependency version conflicts in requirements.txt
**Solution**: 
- Simplified requirements.txt to basic dependencies: `boto3`, `requests`, `aws-xray-sdk`
- Removed unused aiohttp import from code
- Successfully deployed updated Lambda package

### Issue 5: Missing Shared Modules
**Problem**: `No module named 'shared'` error
**Root Cause**: Lambda packaging script only copied function directory, not shared utilities
**Solution**: 
- Copied shared directory to Lambda function directory before packaging
- Updated Lambda function with shared modules included
- Verified successful deployment

### Issue 6: Environment Variable Mismatch
**Problem**: Lambda function failing with "NoSuchBucket" error despite bucket existing
**Root Cause**: Code expected `SAM_EXTRACTED_JSON_RESOURCES_BUCKET` but Lambda had `OUTPUT_BUCKET`
**Investigation Steps**:
1. Checked bucket existence and permissions ✅
2. Verified IAM role permissions ✅  
3. Tested manual S3 write access ✅
4. Discovered environment variable name mismatch ❌

**Solution**:
- Updated Lambda environment variables to match code expectations:
  ```json
  {
    "SAM_EXTRACTED_JSON_RESOURCES_BUCKET": "ktest-sam-extracted-json-resources-dev",
    "SAM_DATA_IN_BUCKET": "ktest-sam-data-in-dev",
    "MAX_CONCURRENT_DOWNLOADS": "10",
    "X_AMZN_TRACE_ID": "ai-rfp-response-agent-phase2-dev-sam-json-processor"
  }
  ```

### Issue 7: Resource Links Field Name Mismatch
**Problem**: Resource files not being downloaded
**Root Cause**: Code looked for `resource_links` but JSON contained `resourceLinks` (camelCase)
**Solution**: 
- Changed `opportunity.get('resource_links', [])` to `opportunity.get('resourceLinks', [])`
- Updated and redeployed Lambda function

### Issue 8: Poor Resource File Naming
**Problem**: Multiple resource files overwriting each other due to generic naming (`<opportunityid>_download`)
**Requirements**: 
- Extract original filenames from downloads
- Use `<opportunityid>_<original_filename>` format
- Change `opportunity.json` to `<opportunityid>_opportunity.json`

**Solution Implemented**:
1. **Enhanced filename extraction**:
   - Try Content-Disposition header first
   - Fall back to URL path parsing
   - Extract file IDs from SAM.gov URLs
   - Use sequential numbering with descriptive names as fallback

2. **Updated file naming**:
   - Opportunity JSON: `<opportunityid>_opportunity.json`
   - Resource files: `<opportunityid>_<extracted_filename>`
   - Added file index parameter for unique naming

3. **Code changes**:
   ```python
   # Updated opportunity file naming
   opportunity_file_key = f"{opportunity_folder}{opportunity_number}_opportunity.json"
   
   # Enhanced resource filename extraction
   def _extract_filename_from_url(self, url: str, file_index: int) -> str:
       # Try Content-Disposition header
       # Fall back to URL parsing
       # Use sequential naming as fallback
   ```

## Final Test Results

### ✅ **Successful Processing**:
- **Files processed**: 1 SAM opportunities file
- **Opportunities extracted**: 178 individual opportunities  
- **Errors**: 0
- **Resource files downloaded**: Hundreds of attachments with proper naming

### ✅ **File Naming Examples**:
- `75H70125R00066_opportunity.json`
- `75H70125R00066_Attachment J01 Lame Deer Construction Plans.pdf`
- `FA813725R0035_Solicitation - FA813725R0035 for WWYK190068.pdf`
- `N6945025R0003_J-0200000-04 Partnering Agreement.pdf`

### ✅ **Processing Statistics**:
- **Total opportunities**: 178
- **Opportunities with attachments**: ~50+
- **Total files created**: 500+ (opportunities + attachments)
- **File types supported**: PDF, Excel (.xlsx), Word (.docx), ZIP files
- **Largest opportunity**: FA813725R0035 with 85+ attachment files

## Key Learnings

1. **Environment Variable Consistency**: Ensure Lambda environment variables match code expectations
2. **JSON Field Naming**: Pay attention to camelCase vs snake_case in API responses
3. **File Naming Strategy**: Important for multi-file downloads to prevent overwrites
4. **Dependency Management**: Keep Lambda dependencies minimal to avoid conflicts
5. **Shared Module Packaging**: Ensure shared utilities are included in Lambda packages

## Commands Used

### Cleanup Commands:
```powershell
Remove-Item -Recurse -Force "src\shared\__pycache__"
Remove-Item -Recurse -Force "src\shared\tests\__pycache__"
$env:AWS_PAGER = ""
```

### Deployment Commands:
```powershell
.\infrastructure\scripts\update-lambda-code.ps1 -Environment "dev" -TemplatesBucket "m2-sam-templates-bucket" -LambdaName "sam-json-processor" -BucketPrefix "ktest"
```

### Testing Commands:
```powershell
aws lambda invoke --function-name ktest-sam-json-processor-dev --cli-binary-format raw-in-base64-out --payload file://test-payload.json response.json
aws s3 ls s3://ktest-sam-extracted-json-resources-dev/ --recursive
```

### Environment Update:
```powershell
aws lambda update-function-configuration --function-name ktest-sam-json-processor-dev --environment file://lambda-env.json
```

## Next Steps
- ✅ Opportunity processing is fully functional
- ✅ Resource file downloading working with proper naming
- 🔄 Ready to test SQS message processing and AI matching (Task 6.3)

## Files Modified
- `src/lambdas/sam-json-processor/lambda_function.py` - Fixed resource links field name and enhanced filename extraction
- `src/lambdas/sam-json-processor/requirements.txt` - Simplified dependencies
- `.gitignore` - Added comprehensive Python and AWS ignore patterns
- `lambda-env.json` - Created for environment variable updates

## Status: ✅ COMPLETED
The opportunity processing system is now fully functional and ready for the next phase of testing (AI matching and analysis).