"""
HTML dashboard generation utilities.
Creates responsive HTML dashboards with CSS styling for web hosting.
"""

import json
from datetime import datetime
from typing import Dict, List, Any
from shared import get_logger, aws_clients
from data_aggregator import DailyStats

logger = get_logger(__name__)

class DashboardGenerator:
    """Generates HTML dashboards from aggregated data."""
    
    def __init__(self):
        self.template = self._get_html_template()
    
    def generate_html(self, daily_stats: DailyStats) -> str:
        """
        Generate rich HTML dashboard matching external version exactly.
        
        Args:
            daily_stats: Aggregated daily statistics
            
        Returns:
            Complete HTML content for the dashboard
        """
        logger.info(f"Generating HTML dashboard", date=daily_stats.date)
        
        try:
            # Format date for display
            formatted_date = self._format_date_for_display(daily_stats.date)
            
            # Group opportunities by confidence score
            from data_aggregator import DataAggregator
            aggregator = DataAggregator()
            grouped = aggregator.group_by_confidence(daily_stats.all_records)
            
            # Generate rich dashboard with confidence groups
            html_content = self._render_rich_dashboard(formatted_date, daily_stats, grouped)
            
            logger.info(f"HTML dashboard generated successfully", 
                       date=daily_stats.date, 
                       content_length=len(html_content))
            
            return html_content
            
        except Exception as e:
            logger.error(f"Error generating HTML dashboard: {str(e)}", date=daily_stats.date)
            raise
    
    def _format_date_for_display(self, date_prefix: str) -> str:
        """
        Format date prefix for display.
        
        Args:
            date_prefix: Date in YYYYMMDD format
            
        Returns:
            Formatted date string
        """
        try:
            dt = datetime.strptime(date_prefix, '%Y%m%d')
            return dt.strftime('%B %d, %Y')
        except Exception:
            return date_prefix
    
    def _generate_enhanced_summary_section(self, daily_stats: DailyStats) -> str:
        """Generate enhanced summary statistics section with Bootstrap cards."""
        return f"""
        <div class="row">
            <div class="col-md-3 mb-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="card-title text-primary">{daily_stats.total_opportunities:,}</h3>
                        <p class="card-text">Total Opportunities</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="card text-center border-success">
                    <div class="card-body">
                        <h3 class="card-title text-success">{daily_stats.matches_found:,}</h3>
                        <p class="card-text">Matches Found</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="card text-center border-warning">
                    <div class="card-body">
                        <h3 class="card-title text-warning">{daily_stats.no_matches:,}</h3>
                        <p class="card-text">No Matches</p>
                    </div>
                </div>
            </div>
            <div class="col-md-3 mb-3">
                <div class="card text-center">
                    <div class="card-body">
                        <h3 class="card-title text-info">{daily_stats.average_match_score:.3f}</h3>
                        <p class="card-text">Average Score</p>
                    </div>
                </div>
            </div>
        </div>
        """
    
    def _generate_summary_section(self, daily_stats: DailyStats) -> str:
        """Legacy method - kept for compatibility."""
        return self._generate_enhanced_summary_section(daily_stats)
    
    def _generate_charts_section(self, daily_stats: DailyStats) -> str:
        """Generate charts and visualizations section."""
        score_distribution_chart = self._generate_score_distribution_chart(daily_stats.match_score_distribution)
        hourly_distribution_chart = self._generate_hourly_distribution_chart(daily_stats.hourly_distribution)
        
        return f"""
        <div class="charts-grid">
            <div class="chart-container">
                <h3>Match Score Distribution</h3>
                {score_distribution_chart}
            </div>
            <div class="chart-container">
                <h3>Processing Activity by Hour</h3>
                {hourly_distribution_chart}
            </div>
        </div>
        """
    
    def _generate_score_distribution_chart(self, distribution: Dict[str, int]) -> str:
        """Generate match score distribution chart."""
        if not distribution or sum(distribution.values()) == 0:
            return '<div class="no-data">No match score data available</div>'
        
        total = sum(distribution.values())
        bars = []
        
        for range_label, count in distribution.items():
            percentage = (count / total) * 100 if total > 0 else 0
            bars.append(f"""
                <div class="bar-item">
                    <div class="bar-label">{range_label}</div>
                    <div class="bar-container">
                        <div class="bar-fill" style="width: {percentage}%"></div>
                        <div class="bar-value">{count}</div>
                    </div>
                </div>
            """)
        
        return f'<div class="bar-chart">{"".join(bars)}</div>'
    
    def _generate_hourly_distribution_chart(self, distribution: Dict[str, int]) -> str:
        """Generate hourly processing distribution chart."""
        if not distribution:
            return '<div class="no-data">No hourly data available</div>'
        
        # Sort by hour
        sorted_hours = sorted(distribution.items())
        max_count = max(distribution.values()) if distribution.values() else 1
        
        bars = []
        for hour, count in sorted_hours:
            height = (count / max_count) * 100 if max_count > 0 else 0
            bars.append(f"""
                <div class="hour-bar">
                    <div class="hour-fill" style="height: {height}%"></div>
                    <div class="hour-label">{hour}</div>
                    <div class="hour-count">{count}</div>
                </div>
            """)
        
        return f'<div class="hour-chart">{"".join(bars)}</div>'
    
    def generate_index_page(self, bucket_name: str) -> str:
        """
        Generate index page showing all available dashboards.
        
        Args:
            bucket_name: S3 bucket name to list dashboards from
            
        Returns:
            HTML content for index page
        """
        try:
            logger.info("Generating index page", bucket=bucket_name)
            
            # Simple approach - just show a basic index for now
            # In a production system, we'd list and parse all manifest files
            cards_html = '<div class="col-12"><div class="alert alert-info text-center">Dashboard index is being generated. Check back soon for available reports.</div></div>'
            
            return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SAM Opportunity Dashboard Index</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container py-5">
        <div class="row mb-4">
            <div class="col-12 text-center">
                <h1 class="display-4 mb-3"><i class="bi bi-list-check me-3"></i>SAM Opportunity Dashboards</h1>
                <p class="lead text-muted">Daily opportunity matching reports and analytics</p>
            </div>
        </div>
        <div class="row">
            {cards_html}
        </div>
        <footer class="mt-5 border-top pt-3 text-muted text-center">
            <p>Generated on {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}</p>
            <p>SAM AI-powered RFP Response Agent</p>
        </footer>
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""
            
        except Exception as e:
            logger.error(f"Error generating index page: {str(e)}")
            return self._generate_error_page(f"Error generating index page: {str(e)}")
    
    def generate_root_redirect(self) -> str:
        """
        Generate root index.html that redirects to dashboards/index.html.
        
        Returns:
            HTML content for root redirect page
        """
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="refresh" content="0; url=dashboards/index.html">
    <title>Redirecting to SAM Opportunity Dashboards...</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light d-flex align-items-center justify-content-center" style="min-height: 100vh;">
    <div class="text-center">
        <div class="spinner-border text-primary mb-3" role="status">
            <span class="visually-hidden">Loading...</span>
        </div>
        <h3>Redirecting to SAM Opportunity Dashboards...</h3>
        <p class="text-muted">If you're not redirected automatically, 
            <a href="dashboards/index.html">click here</a>.</p>
    </div>
    <script>
        // Fallback redirect in case meta refresh doesn't work
        setTimeout(() => window.location.href = 'dashboards/index.html', 1000);
    </script>
</body>
</html>"""
    
    def _render_rich_dashboard(self, formatted_date: str, stats: DailyStats, grouped: Dict[str, List[Dict[str, Any]]]) -> str:
        """Render rich Bootstrap dashboard with confidence groups matching external version exactly."""
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Opportunity Summary {stats.date}</title>
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
          <h1 class="card-title mb-3"><i class="bi bi-clipboard-data me-2"></i> Opportunity Summary {stats.date}</h1>
          <div class="row">
            <div class="col-md-3"><h3>{stats.total_opportunities}</h3><p>Total</p></div>
            <div class="col-md-3"><h3>{stats.matches_found}</h3><p>Matched</p></div>
            <div class="col-md-3"><h3>{stats.average_match_score:.2f}</h3><p>Avg Score</p></div>
            <div class="col-md-3"><h3>{stats.agencies}</h3><p>Agencies</p></div>
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
    <div id="{collapse_id}" class="{collapse_class}">
      <div class="card-body">
        <div class="row">"""

            for r in opps:
                html += self._render_opportunity_card(r, idx)

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

    def _render_opportunity_card(self, r: Dict[str, Any], idx: int) -> str:
        """Render individual opportunity card with all details."""
        title = self._escape_html(r.get('title', 'No title'))
        sol = self._escape_html(r.get('solicitation_id', ''))
        agency = self._escape_html(r.get('agency', ''))
        score = r.get('match_score', 0.0)
        matched = r.get('matched', False)
        rationale = self._escape_html(r.get('rationale', ''))
        desc = r.get('enhanced_description', '')
        skills_req = r.get('opportunity_required_skills', [])
        skills_comp = r.get('company_skills', [])
        past_perf = r.get('past_performance', [])
        citations = r.get('citations', [])
        
        # Metadata
        posted_date = self._format_date(r.get('timestamp', ''))
        deadline = self._format_date(r.get('deadline', ''))
        opp_type = self._escape_html(r.get('type', 'Not specified'))
        
        # Handle POC data
        poc_data = r.get('pointOfContact', {})
        if isinstance(poc_data, dict):
            poc_name = self._escape_html(poc_data.get('fullName', 'Not specified'))
            poc_email = self._escape_html(poc_data.get('email', ''))
        else:
            poc_name = 'Not specified'
            poc_email = ''

        match_badge = '<span class="badge bg-success">Matched</span>' if matched else ''

        skills_req_html = "".join(f"<li>{self._escape_html(s)}</li>" for s in skills_req[:8])
        if len(skills_req) > 8:
            skills_req_html += f"<li>...and {len(skills_req)-8} more</li>"

        skills_comp_html = "".join(f"<li>{self._escape_html(s)}</li>" for s in skills_comp[:8])
        if len(skills_comp) > 8:
            skills_comp_html += f"<li>...and {len(skills_comp)-8} more</li>"
        
        # Past Performance badges
        past_perf_html = ""
        if past_perf:
            past_perf_badges = "".join(
                f'<span class="badge past-performance-badge text-bg-success">{self._escape_html(p)}</span> '
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
            sorted_citations = self._sort_citations_by_doc_number(citations)
            citations_accordion = ""
            for cit_idx, citation in enumerate(sorted_citations):
                doc_title = self._escape_html(citation.get('document_title', 'Unknown'))
                excerpt = self._escape_html(citation.get('excerpt', ''))
                
                # Extract filename from kb_retrieval_results if available
                filename = ""
                kb_results = r.get('kb_retrieval_results', [])
                for kb in kb_results:
                    if kb.get('title') == citation.get('document_title'):
                        source_uri = kb.get('source', '')
                        filename = self._extract_filename_from_uri(source_uri)
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

        return f"""
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

    def _generate_error_page(self, error_message: str) -> str:
        """Generate a simple error page."""
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Error - SAM Dashboards</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body class="bg-light">
    <div class="container py-5">
        <div class="alert alert-danger text-center">
            <h4>Error</h4>
            <p>{self._escape_html(error_message)}</p>
        </div>
    </div>
</body>
</html>"""
    
    def _generate_enhanced_top_matches_section(self, daily_stats: DailyStats) -> str:
        """Generate section showing all opportunities processed that day with Bootstrap styling."""
        if not daily_stats.top_matches:
            return '<div class="alert alert-info text-center">No opportunities were processed on this date</div>'
        
        matches_html = []
        # Sort by match score (highest first) but show all opportunities
        sorted_matches = sorted(daily_stats.top_matches, key=lambda x: x.get('match_score', 0), reverse=True)
        
        for i, match in enumerate(sorted_matches, 1):
            score_class = self._get_bootstrap_score_class(match['match_score'])
            deadline = self._escape_html(str(match.get('deadline', 'Not specified')))
            value = self._escape_html(str(match.get('value', 'Not specified')))
            title = self._escape_html(match['title'][:150])
            if len(match['title']) > 150:
                title += '...'
            
            # Add match status indicator
            match_status = "✅ Matched" if match['match_score'] > 0 else "❌ No Match"
            status_class = "text-success" if match['match_score'] > 0 else "text-danger"
            
            matches_html.append(f"""
                <div class="card mb-3">
                    <div class="card-body">
                        <div class="d-flex justify-content-between align-items-start mb-2">
                            <h5 class="card-title mb-0">#{i} {title}</h5>
                            <div class="text-end">
                                <span class="badge {score_class} fs-6">{match['match_score']:.3f}</span>
                                <br><small class="{status_class}">{match_status}</small>
                            </div>
                        </div>
                        <div class="row">
                            <div class="col-md-4">
                                <small class="text-muted">Solicitation ID:</small><br>
                                <strong>{self._escape_html(match['solicitation_id'])}</strong>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Value:</small><br>
                                <strong>{value}</strong>
                            </div>
                            <div class="col-md-4">
                                <small class="text-muted">Deadline:</small><br>
                                <strong>{deadline}</strong>
                            </div>
                        </div>
                    </div>
                </div>
            """)
        
        return f'<div class="matches-container">{"".join(matches_html)}</div>'
    
    def _generate_top_matches_section(self, daily_stats: DailyStats) -> str:
        """Legacy method - kept for compatibility."""
        return self._generate_enhanced_top_matches_section(daily_stats)
    
    def _generate_performance_section(self, daily_stats: DailyStats) -> str:
        """Generate system performance section."""
        avg_processing_time = (daily_stats.total_processing_time / daily_stats.run_count) if daily_stats.run_count > 0 else 0
        
        return f"""
        <div class="performance-grid">
            <div class="perf-item">
                <div class="perf-label">Total Runs</div>
                <div class="perf-value">{daily_stats.run_count:,}</div>
            </div>
            <div class="perf-item">
                <div class="perf-label">Total Processing Time</div>
                <div class="perf-value">{self._format_duration(daily_stats.total_processing_time)}</div>
            </div>
            <div class="perf-item">
                <div class="perf-label">Average Run Time</div>
                <div class="perf-value">{self._format_duration(avg_processing_time)}</div>
            </div>
            <div class="perf-item">
                <div class="perf-label">Opportunities/Hour</div>
                <div class="perf-value">{self._calculate_throughput(daily_stats):,.1f}</div>
            </div>
        </div>
        """
    
    def _get_bootstrap_score_class(self, score: float) -> str:
        """Get Bootstrap badge class for match score."""
        if score >= 0.8:
            return 'bg-success'
        elif score >= 0.6:
            return 'bg-primary'
        elif score >= 0.4:
            return 'bg-warning'
        else:
            return 'bg-danger'
    
    def _get_score_class(self, score: float) -> str:
        """Legacy method - kept for compatibility."""
        return self._get_bootstrap_score_class(score)
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ''
        return (str(text).replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#x27;'))
    
    def _format_date(self, date_str: str) -> str:
        """Format ISO date string to readable format."""
        if not date_str:
            return "Not specified"
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime("%b %d, %Y %H:%M %Z")
        except:
            return date_str
    
    def _extract_filename_from_uri(self, uri: str) -> str:
        """Extract filename from S3 URI."""
        if not uri:
            return ""
        return uri.split("/")[-1]
    
    def _sort_citations_by_doc_number(self, citations: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort citations by document number."""
        import re
        def extract_number(citation):
            title = citation.get('document_title', '')
            match = re.search(r'Document (\d+)', title)
            return int(match.group(1)) if match else 999
        
        return sorted(citations, key=extract_number)
    
    def _format_duration(self, seconds: float) -> str:
        """Format duration in human-readable format."""
        if seconds < 60:
            return f"{seconds:.1f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"
    
    def _calculate_throughput(self, daily_stats: DailyStats) -> float:
        """Calculate opportunities processed per hour."""
        if daily_stats.total_processing_time <= 0:
            return 0.0
        hours = daily_stats.total_processing_time / 3600
        return daily_stats.total_opportunities / hours if hours > 0 else 0.0
    
    def _get_html_template(self) -> str:
        """
        Get the enhanced HTML template for dashboard generation with Bootstrap styling.
        
        Returns:
            HTML template string with placeholders
        """
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SAM Opportunity Dashboard - {date}</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css" rel="stylesheet">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: #f5f7fa;
            color: #2d3748;
            line-height: 1.6;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
        }}
        
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 2rem;
            border-radius: 12px;
            margin-bottom: 2rem;
            text-align: center;
        }}
        
        .header h1 {{
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            font-weight: 700;
        }}
        
        .header p {{
            font-size: 1.1rem;
            opacity: 0.9;
        }}
        
        .section {{
            background: white;
            border-radius: 12px;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.05);
        }}
        
        .section h2 {{
            font-size: 1.8rem;
            margin-bottom: 1.5rem;
            color: #2d3748;
            border-bottom: 3px solid #667eea;
            padding-bottom: 0.5rem;
        }}
        
        .summary-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
            margin-bottom: 2rem;
        }}
        
        .stat-card {{
            background: #f8fafc;
            border: 2px solid #e2e8f0;
            border-radius: 8px;
            padding: 1.5rem;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 0, 0, 0.1);
        }}
        
        .stat-card.success {{
            border-color: #48bb78;
            background: #f0fff4;
        }}
        
        .stat-card.neutral {{
            border-color: #ed8936;
            background: #fffaf0;
        }}
        
        .stat-card.error {{
            border-color: #f56565;
            background: #fff5f5;
        }}
        
        .stat-number {{
            font-size: 2.5rem;
            font-weight: 700;
            color: #2d3748;
            margin-bottom: 0.5rem;
        }}
        
        .stat-label {{
            font-size: 0.9rem;
            color: #718096;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        
        .charts-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 2rem;
        }}
        
        .chart-container {{
            background: #f8fafc;
            border-radius: 8px;
            padding: 1.5rem;
        }}
        
        .chart-container h3 {{
            font-size: 1.3rem;
            margin-bottom: 1rem;
            color: #2d3748;
        }}
        
        .bar-chart {{
            display: flex;
            flex-direction: column;
            gap: 0.8rem;
        }}
        
        .bar-item {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .bar-label {{
            min-width: 80px;
            font-size: 0.9rem;
            font-weight: 500;
        }}
        
        .bar-container {{
            flex: 1;
            position: relative;
            background: #e2e8f0;
            border-radius: 4px;
            height: 30px;
            display: flex;
            align-items: center;
        }}
        
        .bar-fill {{
            background: linear-gradient(90deg, #667eea, #764ba2);
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s ease;
        }}
        
        .bar-value {{
            position: absolute;
            right: 8px;
            font-size: 0.8rem;
            font-weight: 600;
            color: #2d3748;
        }}
        
        .hour-chart {{
            display: flex;
            align-items: end;
            gap: 0.5rem;
            height: 200px;
            padding: 1rem 0;
        }}
        
        .hour-bar {{
            flex: 1;
            display: flex;
            flex-direction: column;
            align-items: center;
            position: relative;
        }}
        
        .hour-fill {{
            background: linear-gradient(180deg, #667eea, #764ba2);
            width: 100%;
            border-radius: 4px 4px 0 0;
            transition: height 0.3s ease;
            min-height: 2px;
        }}
        
        .hour-label {{
            font-size: 0.7rem;
            margin-top: 0.5rem;
            color: #718096;
        }}
        
        .hour-count {{
            font-size: 0.8rem;
            font-weight: 600;
            margin-top: 0.2rem;
        }}
        
        .matches-list {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .match-item {{
            display: flex;
            align-items: center;
            gap: 1rem;
            padding: 1rem;
            background: #f8fafc;
            border-radius: 8px;
            border-left: 4px solid #667eea;
        }}
        
        .match-rank {{
            font-size: 1.2rem;
            font-weight: 700;
            color: #667eea;
            min-width: 40px;
        }}
        
        .match-content {{
            flex: 1;
        }}
        
        .match-header {{
            display: flex;
            justify-content: space-between;
            align-items: start;
            margin-bottom: 0.5rem;
        }}
        
        .match-title {{
            font-weight: 600;
            color: #2d3748;
            flex: 1;
            margin-right: 1rem;
        }}
        
        .match-score {{
            font-weight: 700;
            padding: 0.25rem 0.75rem;
            border-radius: 20px;
            font-size: 0.9rem;
        }}
        
        .score-excellent {{
            background: #c6f6d5;
            color: #22543d;
        }}
        
        .score-good {{
            background: #bee3f8;
            color: #2a4365;
        }}
        
        .score-fair {{
            background: #feebc8;
            color: #744210;
        }}
        
        .score-poor {{
            background: #fed7d7;
            color: #742a2a;
        }}
        
        .match-details {{
            display: flex;
            gap: 1rem;
            font-size: 0.8rem;
            color: #718096;
        }}
        
        .match-details span {{
            background: white;
            padding: 0.25rem 0.5rem;
            border-radius: 4px;
        }}
        
        .performance-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1.5rem;
        }}
        
        .perf-item {{
            text-align: center;
            padding: 1rem;
            background: #f8fafc;
            border-radius: 8px;
        }}
        
        .perf-label {{
            font-size: 0.9rem;
            color: #718096;
            margin-bottom: 0.5rem;
        }}
        
        .perf-value {{
            font-size: 1.5rem;
            font-weight: 700;
            color: #2d3748;
        }}
        
        .no-data {{
            text-align: center;
            color: #718096;
            font-style: italic;
            padding: 2rem;
        }}
        
        .footer {{
            text-align: center;
            color: #718096;
            font-size: 0.9rem;
            margin-top: 2rem;
            padding: 1rem;
        }}
        
        @media (max-width: 768px) {{
            .container {{
                padding: 10px;
            }}
            
            .header h1 {{
                font-size: 2rem;
            }}
            
            .section {{
                padding: 1rem;
            }}
            
            .summary-grid {{
                grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
                gap: 1rem;
            }}
            
            .charts-grid {{
                grid-template-columns: 1fr;
            }}
            
            .match-header {{
                flex-direction: column;
                align-items: start;
            }}
            
            .match-details {{
                flex-direction: column;
                gap: 0.5rem;
            }}
        }}
    </style>
</head>
<body class="bg-light">
    <div class="container-fluid py-4">
        <!-- Header -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card text-center text-white" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);">
                    <div class="card-body">
                        <h1 class="card-title mb-3"><i class="bi bi-clipboard-data me-2"></i>SAM Opportunity Dashboard</h1>
                        <p class="card-text fs-5">Daily Report for {date}</p>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Summary Statistics -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h2 class="mb-0"><i class="bi bi-bar-chart me-2"></i>Summary Statistics</h2>
                    </div>
                    <div class="card-body">
                        {summary_section}
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Top Opportunity Matches -->
        <div class="row mb-4">
            <div class="col-12">
                <div class="card">
                    <div class="card-header">
                        <h2 class="mb-0"><i class="bi bi-list-ul me-2"></i>Opportunities Processed Today</h2>
                    </div>
                    <div class="card-body">
                        {top_matches_section}
                    </div>
                </div>
            </div>
        </div>
        
        <!-- Footer -->
        <footer class="mt-5 py-4 border-top">
            <div class="container-fluid text-center text-muted">
                <p>Last updated: {last_updated}</p>
                <p>Generated by SAM AI-powered RFP Response Agent</p>
            </div>
        </footer>
    </div>
    
    <!-- Bootstrap JS -->
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>"""