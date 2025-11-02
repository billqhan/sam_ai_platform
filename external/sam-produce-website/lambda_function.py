import json
import boto3
from statistics import mean
from datetime import datetime
import os
import html as html_lib
import re


s3 = boto3.client("s3")

# get website bucket from env var, fallback to input bucket if not set
WEBSITE_BUCKET = os.environ.get("WEBSITE_BUCKET", 'm-sam-website')


# ---- Lambda Handler ----

def lambda_handler(event, context):
    bucket = event["Records"][0]["s3"]["bucket"]["name"]
    key    = event["Records"][0]["s3"]["object"]["key"]

    filename    = key.split("/")[-1]    # e.g. 20250925T1315Z.json
    date_prefix = filename.split("T")[0] # e.g. 20250925

    # 1. Gather all JSON files for this date
    all_keys = list_files_for_date(bucket, "runs/", date_prefix)

    records = []
    for file_key in all_keys:
        records.extend(load_json_records(bucket, file_key))

    if not records:
        return {"status": "no records"}

    # 2. Stats & Grouping
    stats = calculate_stats(records)
    grouped = group_by_confidence(records)

    # 3. Generate daily dashboard (HTML)
    html_daily = render_dashboard(date_prefix, stats, grouped)

    # 4. Write Summary_YYYYMMDD.html
    output_prefix = "dashboards"
    output_html_key = f"{output_prefix}/Summary_{date_prefix}.html"
    s3.put_object(
        Bucket=WEBSITE_BUCKET, Key=output_html_key,
        Body=html_daily.encode("utf-8"), ContentType="text/html"
    )

    # 5. Write manifest JSON for index
    manifest = {
        "date": date_prefix,
        "total": stats["total_opportunities"],
        "matched": stats["matched"],
        "average_score": stats["average_score"],
        "agencies": stats["agencies"],
        "link": f"Summary_{date_prefix}.html"
    }
    output_json_key = f"{output_prefix}/Summary_{date_prefix}.json"
    s3.put_object(
        Bucket=WEBSITE_BUCKET, Key=output_json_key,
        Body=json.dumps(manifest).encode("utf-8"), ContentType="application/json"
    )

    # 6. Update index.html
    index_html = generate_index_page(WEBSITE_BUCKET, output_prefix+"/")
    s3.put_object(
        Bucket=WEBSITE_BUCKET, Key=f"{output_prefix}/index.html",
        Body=index_html.encode("utf-8"), ContentType="text/html"
    )

    # 7. Create/update root redirect
    root_redirect = generate_root_redirect()
    s3.put_object(
        Bucket=WEBSITE_BUCKET, Key="index.html",
        Body=root_redirect.encode("utf-8"), ContentType="text/html"
    )

    return {
        "status": "ok",
        "processed_files": len(all_keys),
        "records": len(records),
        "summary_page": f"s3://{bucket}/{output_html_key}",
        "index_page": f"s3://{bucket}/{output_prefix}/index.html",
        "root_redirect": f"s3://{bucket}/index.html"
    }


# ---- Helpers ----

def list_files_for_date(bucket, prefix, date_prefix):
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=f"{prefix}{date_prefix}")
    return [obj["Key"] for obj in resp.get("Contents", [])]


def load_json_records(bucket, key):
    """Flatten JSON list-of-lists into list of dicts"""
    body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    data = json.loads(body)
    flat = []
    for entry in data:
        if isinstance(entry, list):
            flat.extend(entry)
        elif isinstance(entry, dict):
            flat.append(entry)
    return flat


def calculate_stats(records):
    total = len(records)
    matched = sum(1 for r in records if r.get("matched"))
    avg_score = mean(
        r["score"] for r in records if isinstance(r.get("score"), (int,float))
    ) if records else 0.0
    agencies = len({r.get("fullParentPathName") for r in records if r.get("fullParentPathName")})

    return {
        "total_opportunities": total,
        "matched": matched,
        "average_score": round(avg_score,2),
        "agencies": agencies
    }


def group_by_confidence(records):
    groups = {
        "1.0 (Perfect match)": [],
        "0.9 (Outstanding match)": [],
        "0.8 (Strong match)": [],
        "0.7 (Good subject matter match)": [],
        "0.6 (Decent subject matter match)": [],
        "0.5 (Partial technical or conceptual match)": [],
        "0.3 (Weak or minimal match)": [],
        "0.0 (No demonstrated capability)": []
    }
    
    for r in records:
        s = r.get("score", 0.0)
        if s == 1.0: groups["1.0 (Perfect match)"].append(r)
        elif s == 0.9: groups["0.9 (Outstanding match)"].append(r)
        elif s == 0.8: groups["0.8 (Strong match)"].append(r)
        elif s == 0.7: groups["0.7 (Good subject matter match)"].append(r)
        elif s == 0.6: groups["0.6 (Decent subject matter match)"].append(r)
        elif s == 0.5: groups["0.5 (Partial technical or conceptual match)"].append(r)
        elif s == 0.3: groups["0.3 (Weak or minimal match)"].append(r)
        elif s == 0.0: groups["0.0 (No demonstrated capability)"].append(r)
    
    return groups


def extract_filename_from_uri(uri):
    """Extract filename from S3 URI"""
    if not uri:
        return ""
    return uri.split("/")[-1]


def format_date(date_str):
    """Format ISO date string to readable format"""
    if not date_str:
        return "Not specified"
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime("%b %d, %Y %H:%M %Z")
    except:
        return date_str


def escape_html(text):
    """Escape HTML special characters"""
    if not text:
        return ""
    return html_lib.escape(str(text))


def sort_citations_by_doc_number(citations):
    """Sort citations by document number (e.g., Document 1, Document 2, etc.)"""
    def extract_number(citation):
        title = citation.get('document_title', '')
        match = re.search(r'Document (\d+)', title)
        return int(match.group(1)) if match else 999
    
    return sorted(citations, key=extract_number)


# ---- HTML Generators ----

def render_dashboard(date_prefix, stats, grouped):
    """Rich Bootstrap daily dashboard with enhanced layout"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Opportunity Summary {date_prefix}</title>
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
          <h1 class="card-title mb-3"><i class="bi bi-clipboard-data me-2"></i> Opportunity Summary {date_prefix}</h1>
          <div class="row">
            <div class="col-md-3"><h3>{stats['total_opportunities']}</h3><p>Total</p></div>
            <div class="col-md-3"><h3>{stats['matched']}</h3><p>Matched</p></div>
            <div class="col-md-3"><h3>{stats['average_score']}</h3><p>Avg Score</p></div>
            <div class="col-md-3"><h3>{stats['agencies']}</h3><p>Agencies</p></div>
          </div>
        </div>
      </div>
    </div>
  </div>
"""

    # Confidence groups
    confidence_order = [
        "1.0 (Perfect match)",
        "0.9 (Outstanding match)",
        "0.8 (Strong match)",
        "0.7 (Good subject matter match)",
        "0.6 (Decent subject matter match)",
        "0.5 (Partial technical or conceptual match)",
        "0.3 (Weak or minimal match)",
        "0.0 (No demonstrated capability)"
    ]

    for idx, bucket in enumerate(confidence_order):
        opps = grouped.get(bucket, [])
        if not opps:
            continue
        
        collapse_id = f"collapse-{idx}"
        collapse_class = "collapse"
        
        html += f"""
  <div class="card mb-3">
    <div class="card-header bg-primary text-white d-flex justify-content-between" 
         data-bs-toggle="collapse" data-bs-target="#{collapse_id}" style="cursor:pointer;">
      <h3 class="mb-0">{bucket} 
        <span class="badge bg-light text-dark ms-2">{len(opps)} opportunities</span>
      </h3>
      <i class="bi bi-chevron-down"></i>
    </div>
    <div id="{collapse_id}" class="{ collapse_class}">
      <div class="card-body">
        <div class="row">"""

        for r in opps:
            title = escape_html(r.get('title', 'No title'))
            sol = escape_html(r.get('solicitationNumber', ''))
            agency = escape_html(r.get('fullParentPathName', ''))
            score = r.get('score', 0.0)
            matched = r.get('matched', False)
            rationale = escape_html(r.get('rationale', ''))
            desc = r.get('enhanced_description', '')
            skills_req = r.get('opportunity_required_skills', [])
            skills_comp = r.get('company_skills', [])
            past_perf = r.get('past_performance', [])
            citations = r.get('citations', [])
            
            # Metadata
            posted_date = format_date(r.get('postedDate', ''))
            deadline = format_date(r.get('responseDeadLine', ''))
            opp_type = escape_html(r.get('type', 'Not specified'))
            poc_name = escape_html(r.get('pointOfContact.fullName', 'Not specified'))
            poc_email = escape_html(r.get('pointOfContact.email', ''))

            match_badge = '<span class="badge bg-success">Matched</span>' if matched else ''

            skills_req_html = "".join(f"<li>{escape_html(s)}</li>" for s in skills_req[:8])
            if len(skills_req) > 8:
                skills_req_html += f"<li>...and {len(skills_req)-8} more</li>"

            skills_comp_html = "".join(f"<li>{escape_html(s)}</li>" for s in skills_comp[:8])
            if len(skills_comp) > 8:
                skills_comp_html += f"<li>...and {len(skills_comp)-8} more</li>"
            
            # Past Performance badges
            past_perf_html = ""
            if past_perf:
                past_perf_badges = "".join(
                    f'<span class="badge past-performance-badge text-bg-success">{escape_html(p)}</span> '
                    for p in past_perf
                )
                past_perf_html = f"""
              <div class="mb-3">
                <h6><i class="bi bi-trophy me-1"></i>Past Performance</h6>
                <div class="d-flex flex-wrap gap-2">
                  {past_perf_badges}
                </div>
              </div>"""
            
            # Citations accordion
            citations_html = ""
            if citations:
                sorted_citations = sort_citations_by_doc_number(citations)
                citations_accordion = ""
                for cit_idx, citation in enumerate(sorted_citations):
                    doc_title = escape_html(citation.get('document_title', 'Unknown'))
                    excerpt = escape_html(citation.get('excerpt', ''))
                    
                    # Extract filename from kb_retrieval_results if available
                    filename = ""
                    kb_results = r.get('kb_retrieval_results', [])
                    for kb in kb_results:
                        if kb.get('title') == citation.get('document_title'):
                            source_uri = kb.get('source', '')
                            filename = extract_filename_from_uri(source_uri)
                            break
                    
                    filename_display = f' <span class="text-muted ms-2">({filename})</span>' if filename else ''
                    
                    citations_accordion += f"""
                <div class="accordion-item">
                  <h2 class="accordion-header">
                    <button class="accordion-button collapsed" type="button" data-bs-toggle="collapse" data-bs-target="#citation{idx}-{cit_idx}">
                      <strong>{doc_title}</strong>{filename_display}
                    </button>
                  </h2>
                  <div id="citation{idx}-{cit_idx}" class="accordion-collapse collapse" data-bs-parent="#citationsAccordion{idx}">
                    <div class="accordion-body citation-card">
                      <p class="mb-0"><em>"{excerpt}"</em></p>
                    </div>
                  </div>
                </div>"""
                
                citations_html = f"""
              <h6 class="mt-3"><i class="bi bi-journal-text me-1"></i>Supporting Evidence from Company Documents</h6>
              <div class="accordion mb-3" id="citationsAccordion{idx}">
                {citations_accordion}
              </div>"""

            html += f"""
          <div class="col-12 mb-3">
            <div class="card opportunity-card p-3 shadow-sm">
              <h4>{title} <small class="text-muted">({sol})</small></h4>
              
              <!-- Metadata Badges -->
              <div class="d-flex flex-wrap gap-2 mb-3">
                <span class="badge text-bg-secondary"><i class="bi bi-calendar-event me-1"></i>Posted: {posted_date}</span>
                <span class="badge text-bg-danger"><i class="bi bi-clock me-1"></i>Deadline: {deadline}</span>
                <span class="badge text-bg-light text-dark border"><i class="bi bi-file-text me-1"></i>Type: {opp_type}</span>
                <span class="badge text-bg-info"><i class="bi bi-person me-1"></i>POC: {poc_name}{' (' + poc_email + ')' if poc_email else ''}</span>
              </div>
              
              <p><strong>Agency:</strong> 
                <span class="d-inline-block text-truncate align-bottom" style="max-width: 700px;" title="{agency}">
                  {agency}
                </span>
              </p>
              <p><strong>Score:</strong> {score:.2f} {match_badge}</p>
              
              <h6 class="mt-3"><i class="bi bi-file-earmark-text me-1"></i>Description</h6>
              <div class="md-content border-start border-3 border-primary ps-3 mb-3">{desc}</div>
              
              <h6 class="mt-3"><i class="bi bi-lightbulb me-1"></i>Rationale</h6>
              <div class="border-start border-3 border-warning ps-3 mb-3">
                <p>{rationale}</p>
              </div>
              
              <div class="row mb-3">
                <div class="col-md-6">
                  <h6 class="text-danger"><i class="bi bi-exclamation-triangle me-1"></i>Required Skills</h6>
                  <ul>{skills_req_html}</ul>
                </div>
                <div class="col-md-6">
                  <h6 class="text-success"><i class="bi bi-check-circle me-1"></i>Company Skills</h6>
                  <ul>{skills_comp_html}</ul>
                </div>
              </div>
              
              {past_perf_html}
              
              {citations_html}
              
              <a href="{r.get('uiLink','')}" target="_blank" class="btn btn-primary mt-2"><i class="bi bi-box-arrow-up-right me-1"></i>View Solicitation on SAM.gov</a>
            </div>
          </div>"""

        html += "</div></div></div></div>"

    # Footer
    html += f"""
<footer class="mt-5 py-4 border-top">
  <div class="container-fluid text-center text-muted">
    <p>Generated {timestamp} | Opportunity Dashboard v2.0</p>
  </div>
</footer>

<!-- Bootstrap JS -->
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>

<!-- Marked.js for Markdown Rendering -->
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<script>
  // Render markdown content in .md-content divs
  document.querySelectorAll('.md-content').forEach(el => {{
    const raw = el.textContent || el.innerText;
    el.innerHTML = marked.parse(raw);
  }});
</script>

</div>
</body></html>
"""
    return html


def generate_index_page(bucket, dashboard_prefix="dashboards/"):
    """Bootstrap index showing headline stats per day from JSON manifests"""
    resp = s3.list_objects_v2(Bucket=bucket, Prefix=dashboard_prefix)
    objects = resp.get("Contents", [])
    json_keys = [o["Key"] for o in objects if o["Key"].endswith(".json")]

    daily_stats = []
    for key in json_keys:
        body = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
        try:
            daily_stats.append(json.loads(body))
        except:
            continue

    daily_stats.sort(key=lambda x: x["date"], reverse=True)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Opportunity Report Index</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body class="bg-light">
<div class="container py-5">
  <h1 class="mb-4"><i class="bi bi-list-check"></i> Opportunity Dashboard Index</h1>
  <div class="row row-cols-1 row-cols-md-3 g-4">"""

    if not daily_stats:
        html += "<p>No summaries available yet.</p>"
    else:
        for day in daily_stats:
            html += f"""
    <div class="col">
      <div class="card h-100 shadow-sm">
        <div class="card-body">
          <h4 class="card-title">{day['date']}</h4>
          <ul class="list-group list-group-flush">
            <li class="list-group-item"><strong>Total:</strong> {day['total']}</li>
            <li class="list-group-item"><strong>Matched:</strong> {day['matched']}</li>
            <li class="list-group-item"><strong>Avg Score:</strong> {day['average_score']}</li>
            <li class="list-group-item"><strong>Agencies:</strong> {day['agencies']}</li>
          </ul>
        </div>
        <div class="card-footer text-center">
          <a href="{day['link']}" class="btn btn-primary btn-sm">
            <i class="bi bi-box-arrow-up-right"></i> View Dashboard
          </a>
        </div>
      </div>
    </div>"""

    html += f"""
  </div>
  <footer class="mt-5 border-top pt-3 text-muted text-center">
    <p>Generated on {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</p>
  </footer>
</div>
</body></html>"""

    return html


def generate_root_redirect():
    """Creates a root index.html that redirects to dashboards/index.html"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta http-equiv="refresh" content="0; url=dashboards/index.html">
  <title>Redirecting to Opportunity Dashboards...</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light d-flex align-items-center justify-content-center" style="min-height: 100vh;">
  <div class="text-center">
    <div class="spinner-border text-primary mb-3" role="status">
      <span class="visually-hidden">Loading...</span>
    </div>
    <h3>Redirecting to Opportunity Dashboards...</h3>
    <p class="text-muted">If you're not redirected automatically, 
      <a href="dashboards/index.html">click here</a>.</p>
  </div>
  <script>
    // Fallback redirect in case meta refresh doesn't work
    setTimeout(() => window.location.href = 'dashboards/index.html', 1000);
  </script>
</body>
</html>"""