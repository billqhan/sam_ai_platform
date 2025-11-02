import { useQuery } from '@tanstack/react-query'
import { dashboardApi } from '../services/api'
import {
  TrendingUp,
  TrendingDown,
  FileText,
  Target,
  CheckCircle,
  Clock,
  AlertCircle,
  Activity
} from 'lucide-react'
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer
} from 'recharts'
import { format, parseISO } from 'date-fns'

const COLORS = ['#3b82f6', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6', '#ec4899']

function MetricCard({ title, value, change, icon: Icon, trend, loading }) {
  const isPositive = trend === 'up'
  const TrendIcon = isPositive ? TrendingUp : TrendingDown

  return (
    <div className="card">
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm font-medium text-gray-600">{title}</p>
          <p className="mt-2 text-3xl font-semibold text-gray-900">
            {loading ? (
              <span className="inline-block w-20 h-8 bg-gray-200 rounded animate-pulse"></span>
            ) : (
              value
            )}
          </p>
          {change !== undefined && !loading && (
            <div className="flex items-center mt-2">
              <TrendIcon className={`w-4 h-4 mr-1 ${isPositive ? 'text-success-500' : 'text-danger-500'}`} />
              <span className={`text-sm font-medium ${isPositive ? 'text-success-700' : 'text-danger-700'}`}>
                {change}%
              </span>
              <span className="ml-2 text-sm text-gray-500">vs last week</span>
            </div>
          )}
        </div>
        <div className={`p-3 bg-primary-50 rounded-lg`}>
          <Icon className="w-8 h-8 text-primary-600" />
        </div>
      </div>
    </div>
  )
}

function RecentActivity({ activities, loading }) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center space-x-3">
            <div className="w-10 h-10 bg-gray-200 rounded-full animate-pulse"></div>
            <div className="flex-1 space-y-2">
              <div className="w-3/4 h-4 bg-gray-200 rounded animate-pulse"></div>
              <div className="w-1/2 h-3 bg-gray-200 rounded animate-pulse"></div>
            </div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {activities?.map((activity, index) => (
        <div key={index} className="flex items-start space-x-3">
          <div className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
            activity.type === 'success' ? 'bg-success-50' :
            activity.type === 'warning' ? 'bg-warning-50' :
            activity.type === 'error' ? 'bg-danger-50' : 'bg-primary-50'
          }`}>
            {activity.type === 'success' ? <CheckCircle className="w-5 h-5 text-success-600" /> :
             activity.type === 'warning' ? <AlertCircle className="w-5 h-5 text-warning-600" /> :
             activity.type === 'error' ? <AlertCircle className="w-5 h-5 text-danger-600" /> :
             <Activity className="w-5 h-5 text-primary-600" />}
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-gray-900">{activity.message}</p>
            <p className="text-xs text-gray-500 mt-1">{activity.time}</p>
          </div>
        </div>
      ))}
    </div>
  )
}

function TopMatches({ matches, loading }) {
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="p-4 bg-gray-50 rounded-lg animate-pulse">
            <div className="w-3/4 h-4 mb-2 bg-gray-200 rounded"></div>
            <div className="w-1/2 h-3 bg-gray-200 rounded"></div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {matches?.map((match, index) => (
        <div key={index} className="p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors cursor-pointer">
          <div className="flex items-start justify-between">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-gray-900 truncate">{match.title}</p>
              <p className="mt-1 text-xs text-gray-500">{match.agency}</p>
              <div className="flex items-center mt-2 space-x-2">
                <span className="badge badge-success">
                  Score: {(match.score * 100).toFixed(0)}%
                </span>
                <span className="text-xs text-gray-500">{match.date}</span>
              </div>
            </div>
            <div className="ml-4">
              <div className="text-2xl font-bold text-primary-600">${match.value}</div>
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function Dashboard() {
  const { data: metrics, isLoading: metricsLoading } = useQuery({
    queryKey: ['dashboard-metrics'],
    queryFn: () => dashboardApi.getMetrics(),
    select: (response) => response.data,
  })

  const { data: chartData, isLoading: chartLoading } = useQuery({
    queryKey: ['dashboard-charts', '7d'],
    queryFn: () => dashboardApi.getChartData('opportunities', '7d'),
    select: (response) => response.data,
  })

  const { data: recentActivity, isLoading: activityLoading } = useQuery({
    queryKey: ['dashboard-activity'],
    queryFn: () => dashboardApi.getRecentActivity(5),
    select: (response) => response.data,
  })

  const { data: topMatches, isLoading: matchesLoading } = useQuery({
    queryKey: ['dashboard-top-matches'],
    queryFn: () => dashboardApi.getTopMatches(5),
    select: (response) => response.data,
  })

  // Mock data for demo (replace with API data)
  const mockMetrics = {
    totalOpportunities: 1247,
    totalMatches: 89,
    highQualityMatches: 34,
    pending: 12,
    opportunitiesChange: 12.5,
    matchesChange: -3.2,
    qualityChange: 8.7,
    pendingChange: 15.0,
  }

  const mockChartData = [
    { date: '2025-10-23', opportunities: 45, matches: 8 },
    { date: '2025-10-24', opportunities: 52, matches: 12 },
    { date: '2025-10-25', opportunities: 38, matches: 6 },
    { date: '2025-10-26', opportunities: 61, matches: 15 },
    { date: '2025-10-27', opportunities: 48, matches: 9 },
    { date: '2025-10-28', opportunities: 55, matches: 11 },
    { date: '2025-10-29', opportunities: 67, matches: 14 },
  ]

  const mockCategoryData = [
    { name: 'IT Services', value: 45 },
    { name: 'Engineering', value: 28 },
    { name: 'Consulting', value: 18 },
    { name: 'Manufacturing', value: 12 },
    { name: 'Other', value: 8 },
  ]

  const mockActivity = [
    { type: 'success', message: 'Daily workflow completed successfully', time: '2 hours ago' },
    { type: 'info', message: 'New opportunities downloaded: 67 items', time: '3 hours ago' },
    { type: 'success', message: 'Generated 14 high-quality matches', time: '3 hours ago' },
    { type: 'warning', message: 'Match threshold adjusted to 0.7', time: '1 day ago' },
    { type: 'info', message: 'Weekly report generated', time: '2 days ago' },
  ]

  const mockTopMatches = [
    { 
      title: 'Advanced Radar Systems Integration', 
      agency: 'US Air Force',
      score: 0.92,
      value: '12.5M',
      date: 'Today'
    },
    { 
      title: 'Cybersecurity Infrastructure Modernization', 
      agency: 'Department of Defense',
      score: 0.89,
      value: '8.3M',
      date: 'Yesterday'
    },
    { 
      title: 'Satellite Communication Systems', 
      agency: 'NASA',
      score: 0.87,
      value: '15.2M',
      date: '2 days ago'
    },
    { 
      title: 'Electronic Warfare Systems', 
      agency: 'US Navy',
      score: 0.85,
      value: '9.7M',
      date: '3 days ago'
    },
    { 
      title: 'Command and Control Software', 
      agency: 'US Army',
      score: 0.83,
      value: '6.1M',
      date: '4 days ago'
    },
  ]

  const displayMetrics = metrics || mockMetrics
  const displayChartData = chartData || mockChartData
  const displayActivity = recentActivity || mockActivity
  const displayMatches = topMatches || mockTopMatches

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-gray-900">Dashboard</h1>
        <p className="mt-1 text-sm text-gray-500">
          Overview of RFP opportunities and matches
        </p>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          title="Total Opportunities"
          value={displayMetrics.totalOpportunities?.toLocaleString()}
          change={displayMetrics.opportunitiesChange}
          trend="up"
          icon={FileText}
          loading={metricsLoading}
        />
        <MetricCard
          title="Total Matches"
          value={displayMetrics.totalMatches}
          change={displayMetrics.matchesChange}
          trend="down"
          icon={Target}
          loading={metricsLoading}
        />
        <MetricCard
          title="High Quality Matches"
          value={displayMetrics.highQualityMatches}
          change={displayMetrics.qualityChange}
          trend="up"
          icon={CheckCircle}
          loading={metricsLoading}
        />
        <MetricCard
          title="Pending Review"
          value={displayMetrics.pending}
          change={displayMetrics.pendingChange}
          trend="up"
          icon={Clock}
          loading={metricsLoading}
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Opportunities Trend */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Opportunities Trend (7 Days)</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={displayChartData}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis 
                dataKey="date" 
                tickFormatter={(date) => format(parseISO(date), 'MMM dd')}
              />
              <YAxis />
              <Tooltip 
                labelFormatter={(date) => format(parseISO(date), 'MMM dd, yyyy')}
              />
              <Legend />
              <Line 
                type="monotone" 
                dataKey="opportunities" 
                stroke="#3b82f6" 
                strokeWidth={2}
                name="Opportunities"
              />
              <Line 
                type="monotone" 
                dataKey="matches" 
                stroke="#22c55e" 
                strokeWidth={2}
                name="Matches"
              />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Category Distribution */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Opportunities by Category</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={mockCategoryData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {mockCategoryData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Activity and Matches Grid */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Recent Activity */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Activity</h3>
          <RecentActivity activities={displayActivity} loading={activityLoading} />
        </div>

        {/* Top Matches */}
        <div className="card">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Top Matches</h3>
          <TopMatches matches={displayMatches} loading={matchesLoading} />
        </div>
      </div>
    </div>
  )
}
