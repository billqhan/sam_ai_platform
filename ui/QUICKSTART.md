# UI Quick Start Guide

## 🚀 Quick Setup (5 minutes)

### 1. Install Dependencies
```bash
cd ui
npm install
```

### 2. Start Development Server
```bash
npm run dev
```

The app will run at http://localhost:3000

### 3. View the UI
Open your browser and navigate to http://localhost:3000

## 📊 What You'll See

### Dashboard (Home Page)
- Overview metrics (opportunities, matches, quality scores)
- 7-day trend charts
- Recent activity feed
- Top 5 matches

### Opportunities
- Browse all opportunities from SAM.gov
- Filter by date, category, agency, value
- Search by keywords
- Click any opportunity for full details

### Matches
- View AI-generated matches
- Filter by quality score
- See match analysis and key factors

### Workflow
- Trigger individual workflow steps
- Run full end-to-end workflow
- View execution history
- Configure workflow settings

### Reports
- Access generated dashboards
- Download user response templates
- View report history

### Settings
- Configure company profile
- Adjust matching algorithm
- Set up notifications
- Manage integrations

## 🎨 Current Status

The UI is **fully functional** with:
- ✅ Complete page layouts
- ✅ Navigation system
- ✅ Mock data for demonstration
- ✅ API service layer ready
- ⏳ API backend integration (in progress)

## 🔧 Connecting to Real Data

To connect to your actual AWS backend:

1. Deploy the API Gateway Lambda:
```bash
# Coming soon - API deployment script
```

2. Update environment variable:
```env
# Create ui/.env file
VITE_API_URL=https://your-api-gateway-url.amazonaws.com/prod
```

3. Rebuild:
```bash
npm run build
```

## 🚢 Deploy to AWS

### Option 1: S3 Static Website
```powershell
.\deploy.ps1 -BucketName your-bucket-name -CreateBucket
```

### Option 2: CloudFront + S3
```powershell
# Deploy infrastructure first (CloudFormation template coming soon)
# Then run:
.\deploy.ps1 -BucketName your-bucket-name
```

## 🎯 Next Steps

1. **Try the UI**: Explore all pages and features
2. **Deploy API**: Set up API Gateway and Lambda backend
3. **Connect Services**: Link UI to your AWS infrastructure
4. **Customize**: Update company profile and settings
5. **Production**: Add authentication and CloudFront

## 💡 Tips

- Use the Workflow page to manually trigger processes
- Check Settings to see all configuration options
- The Dashboard updates every 5 seconds (when connected to API)
- All pages support responsive mobile design

## 📞 Need Help?

- Check UI/README.md for full documentation
- Review mock data in page components
- See API service definitions in src/services/api.js
