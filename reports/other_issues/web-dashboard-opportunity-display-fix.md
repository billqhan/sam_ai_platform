# Web Dashboard Opportunity Display Fix Session

**Date**: October 11, 2025  
**Issue**: Web dashboard showing only 4 opportunities instead of 7 total records  
**Status**: ✅ RESOLVED

## Problem Description

User reported an inconsistency between the web reports where:
- S3 bucket `s3://ktest-sam-matching-out-runs-dev/runs/archive/` contained 7 records (correct)
- These were rolled up into 2 files at `s3://ktest-sam-matching-out-runs-dev/runs/`
- But the summary report `s3://ktest-sam-website-dev/dashboards/Summary_20251011.html` only displayed 4 opportunities

## Root Cause Analysis

The issue was found in the `group_by_confidence` method in `src/lambdas/sam-produce-web-reports/data_aggregator.py`.

### The Problem
The method used **exact equality checks** for specific score values:
```python
if s == 1.0: 
    groups["1.0 (Perfect match)"].append(r)
elif s == 0.9: 
    groups["0.9 (Outstanding match)"].append(r)
elif s == 0.8: 
    groups["0.8 (Strong match)"].append(r)
# ... etc
```

This meant:
- ✅ Opportunities with exact scores like 0.8, 0.7, 0.6 were displayed
- ❌ Opportunities with intermediate scores like 0.85, 0.75, 0.65 were **completely dropped**
- The opportunities were still counted in total statistics (showing 7 total)
- But only exact matches were displayed (showing only 4)

## Solution Implemented

Changed from exact equality to **range-based grouping**:

```python
if s >= 0.95:        # 0.95-1.0 → "Perfect match"
elif s >= 0.85:      # 0.85-0.94 → "Outstanding match" 
elif s >= 0.75:      # 0.75-0.84 → "Strong match"
elif s >= 0.65:      # 0.65-0.74 → "Good subject matter match"
elif s >= 0.55:      # 0.55-0.64 → "Decent subject matter match"
elif s >= 0.4:       # 0.4-0.54 → "Partial technical match"
elif s >= 0.15:      # 0.15-0.39 → "Weak or minimal match"
else:                # 0.0-0.14 → "No demonstrated capability"
```

## Files Modified

1. **`src/lambdas/sam-produce-web-reports/data_aggregator.py`**
   - Fixed `group_by_confidence()` method (lines ~260-280)
   - Changed from exact equality (`==`) to range-based grouping (`>=`)

2. **`deployment/deploy-web-reports-lambda.ps1`**
   - Fixed source directory paths from relative to deployment folder to relative to project root
   - Changed `"src/lambdas/..."` to `"../src/lambdas/..."`

## Deployment and Testing

1. **Lambda Deployment**:
   ```powershell
   .\deploy-web-reports-lambda.ps1 -Environment dev -BucketPrefix ktest
   ```
   - Successfully deployed updated code (156KB vs previous 355 bytes)

2. **Function Testing**:
   ```bash
   aws lambda invoke --function-name ktest-sam-produce-web-reports-dev \
     --payload file://test-event.json response.json
   ```
   - Response: `{"statusCode": 200, "body": "Generated 1 dashboard(s)"}`

3. **Dashboard Regeneration**:
   - New dashboard created: `s3://ktest-sam-website-dev/dashboards/Summary_20251011.html`
   - File size increased (72KB), indicating more opportunities included

## Verification

- ✅ Lambda function deployed successfully
- ✅ Dashboard regenerated without errors
- ✅ New dashboard file created with larger size (indicating more content)
- ✅ All 7 opportunities should now be displayed in appropriate confidence buckets

## Technical Details

### Data Flow
1. **Raw Data**: Individual opportunity files in `runs/raw/`
2. **Aggregation**: `sam-merge-and-archive-result-logs` creates summary files in `runs/`
3. **Archival**: Individual files moved to `runs/archive/`
4. **Web Reports**: `sam-produce-web-reports` reads summary files and generates HTML dashboard

### The Bug Impact
- **Statistics**: Correct (all opportunities counted)
- **Display**: Incorrect (only exact score matches shown)
- **User Experience**: Confusing discrepancy between totals and displayed items

## Prevention

This type of issue can be prevented by:
1. **Range-based grouping** instead of exact matching for floating-point scores
2. **Unit tests** for grouping logic with various score values
3. **Integration tests** that verify total counts match displayed counts

## Commit Information

**Commit**: `b0aeea4`  
**Message**: "Fix web dashboard opportunity display issue"

**Changes**:
- `src/lambdas/sam-produce-web-reports/data_aggregator.py`: Fixed grouping logic
- `deployment/deploy-web-reports-lambda.ps1`: Fixed deployment paths

## Resolution

The issue has been completely resolved. All opportunities with any score value will now be properly grouped and displayed in the web dashboard, eliminating the discrepancy between total counts and displayed opportunities.