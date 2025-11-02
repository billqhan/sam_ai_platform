# AI-Powered RFP Response Agent - Web UI

A comprehensive React-based web interface for managing and monitoring the AI-powered RFP response workflow.

## 🎨 Features

### Dashboard
- **Real-time Metrics**: Total opportunities, matches, high-quality matches, pending reviews
- **Trend Analysis**: 7-day charts showing opportunities and matches over time
- **Category Distribution**: Pie chart breaking down opportunities by category
- **Recent Activity**: Live feed of workflow events and system status
- **Top Matches**: Quick view of the highest-scoring opportunities

### Opportunities Browser
- **Advanced Filtering**: Filter by date range, category, agency, value, match status
- **Full-Text Search**: Search across titles, descriptions, and opportunity IDs
- **Detailed View**: Complete opportunity information with documents and contact details
- **AI Match Analysis**: View strengths, opportunities, and risks for each match

### Workflow Control
- **Manual Triggers**: Execute individual workflow steps or full pipeline
- **Real-Time Status**: Monitor workflow execution with live progress indicators
- **Configuration**: Adjust match thresholds, processing limits, and schedules
- **Execution History**: View past workflow runs with detailed logs

### Matches
- **Score-Based Filtering**: View all matches, high-quality only, or medium quality
- **Match Details**: See complete analysis including key match factors
- **Sorting Options**: Sort by score, date, or contract value
- **Quick Actions**: Star favorites, view full details, export to reports

### Reports
- **Web Dashboards**: Daily HTML dashboards with comprehensive opportunity analysis
- **User Reports**: Generated response templates for high-quality matches
- **Download**: Export reports in various formats
- **Email Integration**: Automated delivery to stakeholders

### Settings
- **Company Profile**: Configure company information, capabilities, certifications
- **Matching Algorithm**: Adjust thresholds, weights, and Knowledge Base integration
- **Notifications**: Set up email alerts for different events
- **Integrations**: Manage SAM.gov API and AWS service connections
- **Security**: Configure authentication, MFA, and data protection

## 🛠️ Technology Stack

- **Frontend**: React 18 + Vite
- **Routing**: React Router v6
- **State Management**: TanStack Query (React Query)
- **HTTP Client**: Axios
- **UI Framework**: Tailwind CSS
- **Charts**: Recharts
- **Icons**: Lucide React
- **Date Handling**: date-fns

## 📦 Installation

```bash
cd ui
npm install
```

## 🚀 Development

```bash
# Start development server (runs on port 3000)
npm run dev

# Build for production
npm run build

# Preview production build
npm run preview
```

## 🔧 Configuration

### Environment Variables

Create a `.env` file in the `ui/` directory:

```env
VITE_API_URL=https://your-api-gateway-url.amazonaws.com/prod
```

For local development, the app will proxy `/api` requests to `http://localhost:4000` by default.

## 📁 Project Structure

```
ui/
├── public/                 # Static assets
├── src/
│   ├── components/        # Reusable React components
│   │   └── Layout.jsx     # Main layout with navigation
│   ├── pages/            # Page components
│   │   ├── Dashboard.jsx
│   │   ├── Opportunities.jsx
│   │   ├── OpportunityDetail.jsx
│   │   ├── Matches.jsx
│   │   ├── Workflow.jsx
│   │   ├── Reports.jsx
│   │   └── Settings.jsx
│   ├── services/         # API service layer
│   │   └── api.js       # Axios instance and API methods
│   ├── App.jsx          # Main app component with routing
│   ├── main.jsx         # Entry point
│   └── index.css        # Global styles and Tailwind
├── index.html
├── package.json
├── vite.config.js
├── tailwind.config.js
└── postcss.config.js
```

## 🎯 API Integration

The UI communicates with the backend through a RESTful API. The API client is organized into logical groups:

### Workflow API
- `POST /workflow/download` - Trigger SAM.gov download
- `POST /workflow/process` - Trigger JSON processing
- `POST /workflow/match` - Trigger matching workflow
- `POST /workflow/reports` - Generate reports
- `POST /workflow/notify` - Send notifications
- `GET /workflow/status` - Get current workflow status
- `GET /workflow/history` - Get execution history

### Opportunities API
- `GET /opportunities` - List all opportunities (with filters)
- `GET /opportunities/:id` - Get single opportunity details
- `GET /opportunities/search` - Search opportunities
- `GET /opportunities/categories` - Get available categories
- `GET /opportunities/agencies` - Get available agencies

### Matches API
- `GET /matches` - List all matches (with filters)
- `GET /matches/:id` - Get single match details
- `GET /matches/opportunity/:id` - Get matches for opportunity
- `POST /matches/rerun/:id` - Re-run matching for opportunity

### Reports API
- `GET /reports/latest` - Get latest report
- `GET /reports/history` - Get report history
- `POST /reports/web` - Generate web dashboard
- `POST /reports/user` - Generate user report
- `GET /reports/:id/download` - Download report

### Dashboard API
- `GET /dashboard/metrics` - Get summary metrics
- `GET /dashboard/charts/:type` - Get chart data
- `GET /dashboard/activity` - Get recent activity
- `GET /dashboard/top-matches` - Get top matches

### Settings API
- `GET /settings` - Get all settings
- `PUT /settings` - Update settings
- `GET /settings/profiles` - Get company profiles

## 🎨 Customization

### Theming

Colors are configured in `tailwind.config.js`. The default theme uses:
- Primary: Blue (#3b82f6)
- Success: Green (#22c55e)
- Warning: Orange (#f59e0b)
- Danger: Red (#ef4444)

### Components

Custom components use Tailwind utility classes with semantic CSS classes defined in `index.css`:
- `.btn`, `.btn-primary`, `.btn-secondary`, etc.
- `.card`
- `.input`
- `.badge`, `.badge-success`, `.badge-warning`, etc.

## 📊 Mock Data

For development and demonstration, the UI includes mock data that can be used when the backend API is not available. Mock data is defined inline in each page component and can be replaced with real API responses.

## 🔐 Authentication

The UI is prepared for authentication using JWT tokens stored in localStorage. The API client automatically includes the token in the `Authorization` header for all requests.

To implement authentication:
1. Add login/logout pages
2. Integrate with AWS Cognito or your auth provider
3. Store JWT token on successful login
4. API client will automatically include it in requests

## 🚀 Deployment

### Deploy to S3 + CloudFront

```bash
# Build production bundle
npm run build

# Upload to S3
aws s3 sync dist/ s3://your-bucket-name --delete

# Invalidate CloudFront cache
aws cloudfront create-invalidation --distribution-id YOUR_DIST_ID --paths "/*"
```

### Environment-Specific Builds

```bash
# Production
VITE_API_URL=https://api.example.com npm run build

# Staging
VITE_API_URL=https://api-staging.example.com npm run build
```

## 📝 Development Notes

### Adding New Features

1. **New Page**: Create component in `src/pages/`, add route in `App.jsx`, add navigation link in `Layout.jsx`
2. **New API Endpoint**: Add method in `src/services/api.js`
3. **New Component**: Create in `src/components/` and import where needed

### State Management

- Use TanStack Query for server state (API data)
- Use local component state (`useState`) for UI state
- Use query invalidation to refresh data after mutations

### Best Practices

- Keep components focused and single-purpose
- Use semantic HTML elements
- Maintain accessibility (ARIA labels, keyboard navigation)
- Optimize images and assets
- Use code splitting for large features
- Handle loading and error states consistently

## 🐛 Troubleshooting

### API Requests Fail
- Check VITE_API_URL environment variable
- Verify API Gateway CORS settings
- Check browser console for error details

### Build Errors
- Clear node_modules and reinstall: `rm -rf node_modules && npm install`
- Clear Vite cache: `rm -rf node_modules/.vite`
- Ensure Node.js version ≥ 16

### Styling Issues
- Check Tailwind CSS is processing correctly
- Verify PostCSS configuration
- Clear browser cache

## 📄 License

Proprietary - L3Harris Technologies

## 👥 Support

For questions or issues, contact the development team or refer to the main project documentation.
