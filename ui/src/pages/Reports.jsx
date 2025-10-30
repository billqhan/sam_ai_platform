import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { reportsApi } from '../services/api'
import {
  FileText,
  Download,
  Calendar,
  Eye,
  Mail,
  BarChart3,
  TrendingUp
} from 'lucide-react'
import { format, parseISO } from 'date-fns'

function ReportCard({ report }) {
  return (
    <div className="card hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-start space-x-4">
          <div className={`p-3 rounded-lg ${
            report.type === 'web' ? 'bg-primary-50' : 'bg-success-50'
          }`}>
            {report.type === 'web' ? (
              <BarChart3 className="w-6 h-6 text-primary-600" />
            ) : (
              <FileText className="w-6 h-6 text-success-600" />
            )}
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900">{report.title}</h3>
            <div className="flex items-center mt-2 space-x-4 text-sm text-gray-500">
              <div className="flex items-center">
                <Calendar className="w-4 h-4 mr-1" />
                {format(parseISO(report.generatedDate), 'MMM dd, yyyy')}
              </div>
              {report.emailSent && (
                <div className="flex items-center text-success-600">
                  <Mail className="w-4 h-4 mr-1" />
                  Email sent
                </div>
              )}
            </div>
            {report.summary && (
              <p className="mt-2 text-sm text-gray-600">{report.summary}</p>
            )}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <div className="flex items-center space-x-2">
          {report.opportunities && (
            <span className="badge badge-info">
              {report.opportunities} opportunities
            </span>
          )}
          {report.matches && (
            <span className="badge badge-success">
              {report.matches} matches
            </span>
          )}
        </div>
        <div className="flex items-center space-x-2">
          <button className="btn btn-secondary">
            <Eye className="w-4 h-4 mr-2" />
            View
          </button>
          <button className="btn btn-primary">
            <Download className="w-4 h-4 mr-2" />
            Download
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Reports() {
  const [reportType, setReportType] = useState('all') // all, web, user
  const [dateRange, setDateRange] = useState('7d') // 7d, 30d, 90d, all

  const { data: reports, isLoading } = useQuery({
    queryKey: ['reports', reportType, dateRange],
    queryFn: () => reportsApi.getHistory({ type: reportType, range: dateRange }),
    select: (response) => response.data,
  })

  // Mock data
  const mockReports = [
    {
      id: 'report-001',
      type: 'web',
      title: 'Daily Opportunities Dashboard - October 30, 2025',
      generatedDate: '2025-10-30T08:15:00Z',
      summary: 'Analysis of 67 new opportunities with 14 high-quality matches',
      opportunities: 67,
      matches: 14,
      emailSent: true,
      url: '#',
    },
    {
      id: 'report-002',
      type: 'user',
      title: 'Response Template - Advanced Radar Systems',
      generatedDate: '2025-10-29T14:30:00Z',
      summary: 'Generated response template for opp-001 with 92% match score',
      opportunities: 1,
      matches: 1,
      emailSent: false,
      url: '#',
    },
    {
      id: 'report-003',
      type: 'web',
      title: 'Daily Opportunities Dashboard - October 29, 2025',
      generatedDate: '2025-10-29T08:15:00Z',
      summary: 'Analysis of 55 new opportunities with 11 high-quality matches',
      opportunities: 55,
      matches: 11,
      emailSent: true,
      url: '#',
    },
    {
      id: 'report-004',
      type: 'web',
      title: 'Daily Opportunities Dashboard - October 28, 2025',
      generatedDate: '2025-10-28T08:15:00Z',
      summary: 'Analysis of 48 new opportunities with 9 high-quality matches',
      opportunities: 48,
      matches: 9,
      emailSent: true,
      url: '#',
    },
    {
      id: 'report-005',
      type: 'user',
      title: 'Response Template - Cybersecurity Infrastructure',
      generatedDate: '2025-10-28T11:20:00Z',
      summary: 'Generated response template for opp-002 with 89% match score',
      opportunities: 1,
      matches: 1,
      emailSent: false,
      url: '#',
    },
  ]

  const displayReports = reports || mockReports

  const filteredReports = displayReports.filter(report => {
    if (reportType !== 'all' && report.type !== reportType) return false
    return true
  })

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Reports</h1>
          <p className="mt-1 text-sm text-gray-500">
            Generated dashboards and response templates
          </p>
        </div>
        <button className="btn btn-primary">
          <FileText className="w-5 h-5 mr-2" />
          Generate New Report
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Reports</p>
              <p className="mt-2 text-3xl font-semibold text-gray-900">
                {displayReports.length}
              </p>
            </div>
            <FileText className="w-12 h-12 text-primary-600 opacity-20" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">This Week</p>
              <p className="mt-2 text-3xl font-semibold text-primary-600">
                {displayReports.filter(r => {
                  const date = parseISO(r.generatedDate)
                  const weekAgo = new Date()
                  weekAgo.setDate(weekAgo.getDate() - 7)
                  return date >= weekAgo
                }).length}
              </p>
            </div>
            <Calendar className="w-12 h-12 text-primary-600 opacity-20" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Web Dashboards</p>
              <p className="mt-2 text-3xl font-semibold text-success-600">
                {displayReports.filter(r => r.type === 'web').length}
              </p>
            </div>
            <BarChart3 className="w-12 h-12 text-success-600 opacity-20" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">User Reports</p>
              <p className="mt-2 text-3xl font-semibold text-warning-600">
                {displayReports.filter(r => r.type === 'user').length}
              </p>
            </div>
            <TrendingUp className="w-12 h-12 text-warning-600 opacity-20" />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center space-x-3">
        <select
          value={reportType}
          onChange={(e) => setReportType(e.target.value)}
          className="input w-auto"
        >
          <option value="all">All Reports</option>
          <option value="web">Web Dashboards</option>
          <option value="user">User Reports</option>
        </select>
        <select
          value={dateRange}
          onChange={(e) => setDateRange(e.target.value)}
          className="input w-auto"
        >
          <option value="7d">Last 7 Days</option>
          <option value="30d">Last 30 Days</option>
          <option value="90d">Last 90 Days</option>
          <option value="all">All Time</option>
        </select>
      </div>

      {/* Reports List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-6 bg-gray-200 rounded w-3/4 mb-3"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2"></div>
            </div>
          ))}
        </div>
      ) : filteredReports.length === 0 ? (
        <div className="card text-center py-12">
          <FileText className="w-16 h-16 mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No reports found</h3>
          <p className="text-sm text-gray-500">
            Generate your first report to get started
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredReports.map((report) => (
            <ReportCard key={report.id} report={report} />
          ))}
        </div>
      )}
    </div>
  )
}
