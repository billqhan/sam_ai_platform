"""
HTML dashboard generation utilities.
Creates responsive HTML dashboards with CSS styling for web hosting.
"""

import json
from datetime import datetime
from typing import Dict, List, Any
from shared import get_logger
from .data_aggregator import DailyStats

logger = get_logger(__name__)

class DashboardGenerator:
    """Generates HTML dashboards from aggregated data."""
    
    def __init__(self):
        self.template = self._get_html_template()
    
    def generate_html(self, daily_stats: DailyStats) -> str:
        """
        Generate HTML dashboard from daily statistics.
        
        Args:
            daily_stats: Aggregated daily statistics
            
        Returns:
            Complete HTML content for the dashboard
        """
        logger.info(f"Generating HTML dashboard", date=daily_stats.date)
        
        try:
            # Format date for display
            formatted_date = self._format_date_for_display(daily_stats.date)
            
            # Generate dashboard sections
            summary_section = self._generate_summary_section(daily_stats)
            charts_section = self._generate_charts_section(daily_stats)
            top_matches_section = self._generate_top_matches_section(daily_stats)
            performance_section = self._generate_performance_section(daily_stats)
            
            # Replace template placeholders
            html_content = self.template.format(
                date=formatted_date,
                date_prefix=daily_stats.date,
                summary_section=summary_section,
                charts_section=charts_section,
                top_matches_section=top_matches_section,
                performance_section=performance_section,
                last_updated=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            )
            
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
    
    def _generate_summary_section(self, daily_stats: DailyStats) -> str:
        """Generate summary statistics section."""
        return f"""
        <div class="summary-grid">
            <div class="stat-card">
                <div class="stat-number">{daily_stats.total_opportunities:,}</div>
                <div class="stat-label">Total Opportunities</div>
            </div>
            <div class="stat-card success">
                <div class="stat-number">{daily_stats.matches_found:,}</div>
                <div class="stat-label">Matches Found</div>
            </div>
            <div class="stat-card neutral">
                <div class="stat-number">{daily_stats.no_matches:,}</div>
                <div class="stat-label">No Matches</div>
            </div>
            <div class="stat-card error">
                <div class="stat-number">{daily_stats.errors:,}</div>
                <div class="stat-label">Errors</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{daily_stats.success_rate:.1f}%</div>
                <div class="stat-label">Success Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{daily_stats.average_match_score:.3f}</div>
                <div class="stat-label">Avg Match Score</div>
            </div>
        </div>
        """
    
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
    
    def _generate_top_matches_section(self, daily_stats: DailyStats) -> str:
        """Generate top matches section."""
        if not daily_stats.top_matches:
            return '<div class="no-data">No matches found for this date</div>'
        
        matches_html = []
        for i, match in enumerate(daily_stats.top_matches[:10], 1):
            score_class = self._get_score_class(match['match_score'])
            deadline = match.get('deadline', 'Not specified')
            value = match.get('value', 'Not specified')
            
            matches_html.append(f"""
                <div class="match-item">
                    <div class="match-rank">#{i}</div>
                    <div class="match-content">
                        <div class="match-header">
                            <div class="match-title">{self._escape_html(match['title'][:100])}{'...' if len(match['title']) > 100 else ''}</div>
                            <div class="match-score {score_class}">{match['match_score']:.3f}</div>
                        </div>
                        <div class="match-details">
                            <span class="match-id">ID: {match['solicitation_id']}</span>
                            <span class="match-value">Value: {value}</span>
                            <span class="match-deadline">Deadline: {deadline}</span>
                        </div>
                    </div>
                </div>
            """)
        
        return f'<div class="matches-list">{"".join(matches_html)}</div>'
    
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
    
    def _get_score_class(self, score: float) -> str:
        """Get CSS class for match score."""
        if score >= 0.8:
            return 'score-excellent'
        elif score >= 0.6:
            return 'score-good'
        elif score >= 0.4:
            return 'score-fair'
        else:
            return 'score-poor'
    
    def _escape_html(self, text: str) -> str:
        """Escape HTML special characters."""
        if not text:
            return ''
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&#x27;'))
    
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
        Get the HTML template for dashboard generation.
        
        Returns:
            HTML template string with placeholders
        """
        return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SAM Opportunity Dashboard - {date}</title>
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
<body>
    <div class="container">
        <div class="header">
            <h1>SAM Opportunity Dashboard</h1>
            <p>Daily Report for {date}</p>
        </div>
        
        <div class="section">
            <h2>Summary Statistics</h2>
            {summary_section}
        </div>
        
        <div class="section">
            <h2>Data Visualizations</h2>
            {charts_section}
        </div>
        
        <div class="section">
            <h2>Top Opportunity Matches</h2>
            {top_matches_section}
        </div>
        
        <div class="section">
            <h2>System Performance</h2>
            {performance_section}
        </div>
        
        <div class="footer">
            <p>Last updated: {last_updated}</p>
            <p>Generated by SAM AI-powered RFP Response Agent</p>
        </div>
    </div>
</body>
</html>"""