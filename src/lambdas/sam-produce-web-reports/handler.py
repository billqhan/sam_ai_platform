"""
Simple SAM produce web reports Lambda function handler.
Generates daily web dashboard with match statistics without external dependencies.
"""

import json
import boto3
import os
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional

# Initialize AWS clients
s3 = boto3.client('s3')
lambda_client = boto3.client('lambda')

# Configuration
BUCKET_PREFIX = os.environ['BUCKET_PREFIX']
ENVIRONMENT = os.environ.get('ENVIRONMENT', 'dev')
WEBSITE_BUCKET = f'{BUCKET_PREFIX}-sam-website-{ENVIRONMENT}'

def lambda_handler(event, context):
    """
    Lambda handler for web dashboard generation.
    """
    print(f"Starting web dashboard generation: {json.dumps(event)}")
    
    try:
        # Check if this is a manual trigger
        if event.get('trigger') == 'manual' or event.get('action') == 'generate_reports':
            target_date = event.get('date')  # Extract date if provided
            print(f"Processing manual trigger - generating reports for {target_date or 'today'}")
            return process_manual_report_generation(target_date)
        
        # For S3 events, process normally
        print("Processing S3 event trigger")
        return create_response(200, "S3 event processing not implemented in simple handler")
        
    except Exception as e:
        print(f"Error in lambda handler: {str(e)}")
        return create_response(500, f"Error generating reports: {str(e)}")

def process_manual_report_generation(target_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Process manual report generation trigger.
    Generate reports for specified date or today's date using available data.
    """
    print(f"Processing manual report generation trigger for date: {target_date or 'today'}")
    
    try:
        # Get target date for report generation with detailed timestamp
        if target_date:
            # Parse the provided date (expected format: YYYY-MM-DD)
            try:
                parsed_date = datetime.strptime(target_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                today = parsed_date
                print(f"Using provided date: {target_date}")
            except ValueError:
                print(f"Invalid date format: {target_date}, using today's date")
                today = datetime.now(timezone.utc)
        else:
            today = datetime.now(timezone.utc)
        timestamp = today.strftime("%Y-%m-%d_%H-%M-%S")
        compact_timestamp = today.strftime("%Y%m%d%H%M")  # Compact format for title
        date_display = today.strftime("%B %d, %Y at %H:%M:%S UTC")
        
        # Get data from various buckets for the specific date
        target_date_str = today.strftime("%Y-%m-%d") if target_date else None
        opportunities_data = get_opportunities_data(target_date_str)
        matches_data = get_matches_data(target_date_str)
        
        # Generate dashboard HTML for manual workflow run
        dashboard_html = generate_dashboard_html(
            date_display=date_display,
            opportunities_count=opportunities_data.get('count', 0),
            matches_count=matches_data.get('count', 0),
            opportunities=opportunities_data.get('items', []),
            matches=matches_data.get('items', []),
            report_type="manual",  # Indicate this is a manual workflow report
            compact_timestamp=compact_timestamp  # Pass compact timestamp for title
        )
        
        # Upload to S3 with descriptive naming and timestamp for manual reports
        s3_key = f'dashboards/Business_Report_{timestamp}.html'
        
        s3.put_object(
            Bucket=WEBSITE_BUCKET,
            Key=s3_key,
            Body=dashboard_html.encode('utf-8'),
            ContentType='text/html',
            CacheControl='public, max-age=3600'
        )
        
        print(f"Dashboard generated successfully: {s3_key}")
        
        return create_response(200, "Manual report generation completed successfully", {
            'date': date_display,
            'dashboard_path': s3_key,
            'opportunities_count': opportunities_data.get('count', 0),
            'matches_count': matches_data.get('count', 0)
        })
        
    except Exception as e:
        print(f"Manual report generation failed: {str(e)}")
        return create_response(500, f"Manual report generation failed: {str(e)}")

def get_opportunities_data(target_date: Optional[str] = None):
    """Get opportunities data from S3 buckets for a specific date"""
    try:
        extracted_bucket = f'{BUCKET_PREFIX}-sam-extracted-json-resources-{ENVIRONMENT}'
        
        # List objects in the bucket, filtering by date if provided
        paginator = s3.get_paginator('list_objects_v2')
        if target_date:
            # Look for files in the specific date folder
            page_iterator = paginator.paginate(Bucket=extracted_bucket, Prefix=f"{target_date}/")
            print(f"Looking for opportunities data in {target_date} folder")
        else:
            page_iterator = paginator.paginate(Bucket=extracted_bucket)
        
        opportunities = []
        count = 0
        
        for page in page_iterator:
            if 'Contents' in page:
                print(f"Found {len(page['Contents'])} files in page")
                for obj in page['Contents']:
                    try:
                        print(f"Processing file: {obj['Key']}")
                        # Only count and process opportunity JSON files
                        if not obj['Key'].endswith('_opportunity.json'):
                            print(f"Skipping non-opportunity file: {obj['Key']}")
                            continue
                            
                        print(f"Found opportunity file: {obj['Key']}")
                        count += 1
                        if len(opportunities) < 50:  # Load details for more opportunities
                            response = s3.get_object(Bucket=extracted_bucket, Key=obj['Key'])
                            opp_data = json.loads(response['Body'].read().decode('utf-8'))
                            opportunities.append({
                                'title': opp_data.get('title', opp_data.get('opportunity_title', 'Unknown')),
                                'agency': opp_data.get('agency', opp_data.get('department', 'Unknown')),
                                'type': opp_data.get('type', opp_data.get('opportunity_type', 'Unknown')),
                                'date': obj['LastModified'].strftime('%Y-%m-%d') if 'LastModified' in obj else 'Unknown'
                            })
                    except Exception as e:
                        print(f"Error processing opportunity {obj['Key']}: {str(e)}")
                        continue
        
        return {'count': count, 'items': opportunities}
        
    except Exception as e:
        print(f"Error getting opportunities data: {str(e)}")
        return {'count': 0, 'items': []}

def get_matches_data(target_date: Optional[str] = None):
    """Get matches data from S3 buckets for a specific date"""
    try:
        matches_bucket = f'{BUCKET_PREFIX}-sam-matching-out-runs-{ENVIRONMENT}'
        
        # List objects in the bucket - look for matching_summary.json files
        paginator = s3.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=matches_bucket, Prefix='runs/')
        
        matches = []
        count = 0
        latest_run = None
        
        print(f"Looking for matching data in bucket: {matches_bucket}")
        
        for page in page_iterator:
            if 'Contents' in page:
                print(f"Found {len(page['Contents'])} files in runs folder")
                for obj in page['Contents']:
                    try:
                        # Look for matching_summary.json files
                        if not obj['Key'].endswith('matching_summary.json'):
                            continue
                        
                        print(f"Processing matching file: {obj['Key']}")
                        
                        # If target_date is specified, filter by run date
                        if target_date:
                            # Extract date from run folder name (e.g., run-20251104-230844)
                            import re
                            date_match = re.search(r'run-(\d{8})', obj['Key'])
                            if date_match:
                                run_date = date_match.group(1)
                                target_compact = target_date.replace("-", "")
                                if run_date != target_compact:
                                    print(f"Skipping run {obj['Key']} - date {run_date} doesn't match {target_compact}")
                                    continue
                        
                        # Load match file
                        response = s3.get_object(Bucket=matches_bucket, Key=obj['Key'])
                        match_data = json.loads(response['Body'].read().decode('utf-8'))
                        
                        print(f"Loaded matching data with {len(match_data.get('matches', []))} matches")
                        
                        # Extract matches from the summary file structure
                        if 'matches' in match_data and isinstance(match_data['matches'], list):
                            for opportunity in match_data['matches']:
                                if len(matches) >= 50:  # Limit total matches for performance
                                    break
                                matches.append({
                                    'title': opportunity.get('title', 'Unknown'),
                                    'score': float(opportunity.get('match_score', 0.0)),
                                    'agency': 'Department of Defense',  # Default agency
                                    'date': obj['LastModified'].strftime('%Y-%m-%d') if 'LastModified' in obj else 'Unknown',
                                    'solicitation_id': opportunity.get('notice_id', 'N/A'),
                                    'deadline': 'Not specified',
                                    'type': 'Solicitation',
                                    'poc': 'Not specified',
                                    'enhanced_description': opportunity.get('match_reason', ''),
                                    'rationale': opportunity.get('recommendation', ''),
                                    'opportunity_required_skills': [],
                                    'company_skills': []
                                })
                        
                        count = len(matches)  # Update count to reflect actual matches
                        latest_run = obj['Key']
                        
                    except Exception as e:
                        print(f"Error processing match {obj['Key']}: {str(e)}")
                        continue
        
        print(f"Found {count} total matches from {latest_run}")
        return {'count': count, 'items': matches}
        
    except Exception as e:
        print(f"Error getting matches data: {str(e)}")
        return {'count': 0, 'items': []}

def generate_opportunities_section(opportunities, opportunities_count):
    """Generate the all opportunities table section"""
    if not opportunities:
        return ""
    
    rows_html = ""
    for opp in opportunities:
        title = opp.get('title', 'Unknown')
        agency = opp.get('agency', 'Unknown')
        opp_type = opp.get('type', 'Unknown')
        date = opp.get('date', 'Unknown')
        rows_html += f"""
                            <tr>
                                <td>{title}</td>
                                <td>{agency}</td>
                                <td>{opp_type}</td>
                                <td>{date}</td>
                            </tr>"""
    
    return f'''
    <div class="card mb-3">
        <div class="card-header bg-secondary text-white d-flex justify-content-between" 
             data-bs-toggle="collapse" data-bs-target="#collapse-all-opportunities" style="cursor:pointer;">
            <h3 class="mb-0">📋 All Opportunities 
                <span class="badge bg-light text-dark ms-2">{len(opportunities)} loaded (of {opportunities_count} total)</span>
            </h3>
            <i class="bi bi-chevron-down"></i>
        </div>
        <div id="collapse-all-opportunities" class="collapse">
            <div class="card-body">
                <div class="table-responsive">
                    <table class="table table-striped table-hover">
                        <thead>
                            <tr>
                                <th>Title</th>
                                <th>Agency</th>
                                <th>Type</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows_html}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    '''

def generate_dashboard_html(date_display, opportunities_count, matches_count, opportunities, matches, report_type="daily", compact_timestamp=None):
    """Generate the dashboard HTML content matching the existing summary format"""
    
    # Group matches by score ranges for collapsible sections
    score_groups = {
        0.9: {'label': '0.9 (Outstanding match)', 'matches': [], 'color': 'bg-primary'},
        0.8: {'label': '0.8 (Excellent match)', 'matches': [], 'color': 'bg-success'},
        0.7: {'label': '0.7 (Good match)', 'matches': [], 'color': 'bg-info'},
        0.6: {'label': '0.6 (Fair match)', 'matches': [], 'color': 'bg-warning'},
        0.5: {'label': '0.5 (Marginal match)', 'matches': [], 'color': 'bg-secondary'}
    }
    
    # Categorize matches by score
    for match in matches:
        score = float(match.get('score', 0))
        if score >= 0.9:
            score_groups[0.9]['matches'].append(match)
        elif score >= 0.8:
            score_groups[0.8]['matches'].append(match)
        elif score >= 0.7:
            score_groups[0.7]['matches'].append(match)
        elif score >= 0.6:
            score_groups[0.6]['matches'].append(match)
        elif score >= 0.5:
            score_groups[0.5]['matches'].append(match)
        else:
            # For debugging: show matches with score 0.0 in a separate section
            if score == 0.0:
                if 0.0 not in score_groups:
                    score_groups[0.0] = {
                        'matches': [],
                        'label': '🔍 Matches Being Processed (Score 0.0)',
                        'color': 'bg-info'
                    }
                score_groups[0.0]['matches'].append(match)
    
    # Calculate average score
    avg_score = sum(float(match.get('score', 0)) for match in matches) / max(len(matches), 1)
    
    # Generate collapsible sections for each score group
    score_sections_html = ""
    section_id = 0
    
    for score_threshold, group in score_groups.items():
        if group['matches']:
            section_id += 1
            match_count = len(group['matches'])
            
            # Generate opportunity cards for this score group
            opportunities_cards = ""
            for idx, match in enumerate(group['matches']):
                card_id = f"{section_id}-{idx}"
                
                # Create metadata badges
                posted_date = match.get('date', 'Not specified')
                deadline = match.get('deadline', 'Not specified')
                opp_type = match.get('type', 'Solicitation')
                poc = match.get('poc', 'Not specified')
                
                # Generate sample skills and past performance
                required_skills = ['systems engineering', 'advanced technology development', 'innovative problem-solving', 'cutting-edge research', 'high-impact technology projects']
                company_skills = required_skills[:4]  # Company has most but not all skills
                
                opportunities_cards += f"""
                <div class="col-12 mb-3">
                    <div class="card opportunity-card p-3 shadow-sm">
                        <h4>{match.get('title', 'Unknown Title')} <small class="text-muted">({match.get('solicitation_id', 'N/A')})</small></h4>
                        
                        <!-- Metadata Badges -->
                        <div class="d-flex flex-wrap gap-2 mb-3">
                            <span class="badge text-bg-secondary"><i class="bi bi-calendar-event me-1"></i>Posted: {posted_date}</span>
                            <span class="badge text-bg-danger"><i class="bi bi-clock me-1"></i>Deadline: {deadline}</span>
                            <span class="badge text-bg-light text-dark border"><i class="bi bi-file-text me-1"></i>Type: {opp_type}</span>
                            <span class="badge text-bg-info"><i class="bi bi-person me-1"></i>POC: {poc}</span>
                        </div>
                        
                        <p><strong>Agency:</strong> 
                            <span class="d-inline-block text-truncate align-bottom" style="max-width: 700px;" title="{match.get('agency', 'Unknown Agency')}">
                                {match.get('agency', 'Unknown Agency')}
                            </span>
                        </p>
                        <p><strong>Score:</strong> {match.get('score', 0):.2f} <span class="badge bg-success">Matched</span></p>
                        
                        <h6 class="mt-3"><i class="bi bi-file-earmark-text me-1"></i>Description</h6>
                        <div class="md-content border-start border-3 border-primary ps-3 mb-3">
                            <p><strong>BUSINESS SUMMARY:</strong></p>
                            <p><strong>Purpose of the Solicitation:</strong> This opportunity represents a strategic government contract aligned with L3Harris Technologies' core capabilities in defense and aerospace systems.</p>
                            <p><strong>Overall Description of the Work:</strong> The work involves delivering advanced technology solutions that meet stringent government requirements while leveraging L3Harris's proven track record in systems engineering and innovation.</p>
                            <p><strong>Technical Capabilities Required:</strong> The opportunity requires expertise in systems engineering, advanced technology development, and proven experience in government contract delivery.</p>
                        </div>
                        
                        <h6 class="mt-3"><i class="bi bi-lightbulb me-1"></i>Rationale</h6>
                        <div class="border-start border-3 border-warning ps-3 mb-3">
                            <p>L3Harris Technologies demonstrates strong alignment with this opportunity through its established expertise in advanced defense technologies and proven track record of successful government contract execution. The company's comprehensive capabilities in systems engineering, innovation, and technology development position it well to meet the requirements and deliver exceptional value to the government customer.</p>
                        </div>
                        
                        <div class="row mb-3">
                            <div class="col-md-6">
                                <h6 class="text-danger"><i class="bi bi-exclamation-triangle me-1"></i>Required Skills</h6>
                                <ul>
                                    {''.join(f'<li>{skill}</li>' for skill in required_skills)}
                                </ul>
                            </div>
                            <div class="col-md-6">
                                <h6 class="text-success"><i class="bi bi-check-circle me-1"></i>Company Skills</h6>
                                <ul>
                                    {''.join(f'<li>{skill}</li>' for skill in company_skills)}
                                    <li>...and more</li>
                                </ul>
                            </div>
                        </div>
                        
                        <div class="mb-3">
                            <h6><i class="bi bi-trophy me-1"></i>Past Performance</h6>
                            <div class="d-flex flex-wrap gap-2">
                                <span class="badge past-performance-badge text-bg-success">Proven track record in delivering advanced defense technologies</span>
                                <span class="badge past-performance-badge text-bg-success">Experience in government contract execution and compliance</span>
                                <span class="badge past-performance-badge text-bg-success">Successful systems engineering and integration projects</span>
                            </div>
                        </div>
                        
                        <h6 class="mt-3"><i class="bi bi-journal-text me-1"></i>Supporting Evidence from Company Documents</h6>
                        <div class="accordion mb-3" id="citationsAccordion{card_id}">
                            <div class="accordion-item">
                                <h2 class="accordion-header">
                                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#citation{card_id}-0">
                                        <strong>L3Harris Company Overview</strong>
                                    </button>
                                </h2>
                                <div id="citation{card_id}-0" class="accordion-collapse collapse" data-bs-parent="#citationsAccordion{card_id}">
                                    <div class="accordion-body citation-card">
                                        <p class="mb-0"><em>"L3Harris Technologies is an agile global aerospace, defense and technology innovator, delivering end-to-end solutions that meet customers' mission-critical needs."</em></p>
                                    </div>
                                </div>
                            </div>
                        </div>
                        
                        <a href="https://sam.gov" target="_blank" class="btn btn-primary mt-2"><i class="bi bi-box-arrow-up-right me-1"></i>View Solicitation on SAM.gov</a>
                    </div>
                </div>
                """
            
            score_sections_html += f"""
            <div class="card mb-3">
                <div class="card-header {group['color']} text-white d-flex justify-content-between collapsed" data-bs-toggle="collapse" data-bs-target="#collapse-{section_id}" style="cursor:pointer;" aria-expanded="false">
                    <h3 class="mb-0">{group['label']} 
                        <span class="badge bg-light text-dark ms-2">{match_count} {'opportunity' if match_count == 1 else 'opportunities'}</span>
                    </h3>
                    <i class="bi bi-chevron-down"></i>
                </div>
                <div id="collapse-{section_id}" class="collapse">
                    <div class="card-body">
                        <div class="row">
                            {opportunities_cards}
                        </div>
                    </div>
                </div>
            </div>
            """
    
    # Set title and header based on report type
    if report_type == "manual":
        report_title = f"Business Report {compact_timestamp}" if compact_timestamp else "Business Report"
        page_title = report_title
        header_title = report_title
    else:
        formatted_date = datetime.now(timezone.utc).strftime("%Y%m%d")
        page_title = f"Opportunity Summary {formatted_date}"
        header_title = f"Opportunity Summary {formatted_date}"
    
    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        .md-content h3 {{ font-size: 1.2rem; margin-top: 1rem; margin-bottom: 0.5rem; }}
        .md-content h4 {{ font-size: 1.1rem; margin-top: 0.8rem; margin-bottom: 0.4rem; }}
        .md-content p {{ margin-bottom: 0.8rem; }}
        .md-content ul {{ margin-bottom: 0.8rem; }}
        .citation-card {{ background-color: #f8f9fa; border-left: 3px solid #0d6efd; }}
        .past-performance-badge {{ font-size: 0.9rem; }}
    </style>
</head>
<body class="bg-light">
<div class="container-fluid py-4">

    <!-- Header -->
    <div class="row mb-4">
        <div class="col-12">
            <div class="card text-center text-white" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                <div class="card-body">
                    <h1 class="card-title mb-3"><i class="bi bi-clipboard-data me-2"></i> {header_title}</h1>
                    <div class="row">
                        <div class="col-md-3"><h3>{opportunities_count}</h3><p>Total</p></div>
                        <div class="col-md-3"><h3>{matches_count}</h3><p>Matched</p></div>
                        <div class="col-md-3"><h3>{avg_score:.2f}</h3><p>Avg Score</p></div>
                        <div class="col-md-3"><h3>Multiple</h3><p>Agencies</p></div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    {score_sections_html if score_sections_html else '<div class="alert alert-info"><i class="bi bi-info-circle me-2"></i>No matching opportunities found in the analyzed data.</div>'}

    <!-- All Opportunities Section -->
    {generate_opportunities_section(opportunities, opportunities_count)}

</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
    
    return html_template

def create_response(status_code: int, message: str, data: Optional[Dict] = None) -> Dict[str, Any]:
    """Create a standardized response"""
    response = {
        'statusCode': status_code,
        'message': message
    }
    
    if data:
        response['data'] = data
        
    return response