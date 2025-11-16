import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { reportsApi } from '../services/api'
import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || import.meta.env.VITE_API_URL || '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})
import {
  FileText,
  Download,
  Calendar,
  Eye,
  Mail,
  BarChart3,
  TrendingUp,
  RefreshCw
} from 'lucide-react'
import { format, parseISO } from 'date-fns'

function ReportCard({ report, onViewReport }) {
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
          {report.viewUrl && (
            <button 
              onClick={() => onViewReport(report)} 
              className="btn btn-secondary"
            >
              <Eye className="w-4 h-4 mr-2" />
              View
            </button>
          )}
          <a 
            href={report.downloadUrl} 
            target="_blank" 
            rel="noopener noreferrer"
            className="btn btn-primary"
          >
            <Download className="w-4 h-4 mr-2" />
            Download
          </a>
        </div>
      </div>
    </div>
  )
}

export default function Reports() {
  const [reportType, setReportType] = useState('all') // all, web, user
  const [dateRange, setDateRange] = useState('7d') // 7d, 30d, 90d, all
  const [refreshing, setRefreshing] = useState(false)
  const [page, setPage] = useState(1)
  const [pageSize] = useState(20) // Fixed page size
  const queryClient = useQueryClient()

  const handleViewReport = async (report) => {
    console.log('handleViewReport called with:', report)
    
    try {
      // Fetch the report HTML from API
      const response = await api.get(`/reports/${report.id}/view`)
      
      // Check if response contains HTML (string starting with <!DOCTYPE or <html)
      if (typeof response.data === 'string' && 
          (response.data.trim().startsWith('<!DOCTYPE') || response.data.trim().startsWith('<html'))) {
        // Create a blob with HTML content and open in new tab
        const blob = new Blob([response.data], { type: 'text/html' })
        const url = window.URL.createObjectURL(blob)
        window.open(url, '_blank')
        // Clean up the blob URL after opening
        setTimeout(() => window.URL.revokeObjectURL(url), 1000)
      } else {
        // Fallback: try the downloadUrl
        if (report.downloadUrl) {
          window.open(report.downloadUrl, '_blank')
        } else {
          alert('Report format not recognized')
        }
      }
      
    } catch (error) {
      console.error('Error viewing report:', error)
      
      // Fallback: try the downloadUrl instead
      if (report.downloadUrl) {
        window.open(report.downloadUrl, '_blank')
      } else {
        alert('Unable to open report: ' + error.message)
      }
    }
  }

  const { data: reportsResponse, isLoading, error } = useQuery({
    queryKey: ['reports', reportType, dateRange, page, pageSize],
    queryFn: () => api.get('/reports', { 
      params: { 
        type: reportType, 
        range: dateRange,
        page: page,
        pageSize: pageSize
      } 
    }),
    select: (response) => {
      console.log('Reports API response:', response.data);
      return response.data;
    },
  })

  const reports = reportsResponse?.items || []
  const totalReports = reportsResponse?.total || 0
  const totalPages = reportsResponse?.totalPages || Math.ceil(totalReports / pageSize)

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

  // Map API data to UI format
  const mappedReports = reports ? reports.map(report => ({
    id: report.id,
    type: report.type,
    title: report.title,
    generatedDate: report.generatedDate,
    opportunities: report.opportunities || 0,
    matches: report.matches || 0,
    summary: report.summary,
    emailSent: report.emailSent,
    url: report.viewUrl || report.downloadUrl,
    downloadUrl: report.downloadUrl,
    viewUrl: `${import.meta.env.VITE_API_BASE_URL}/reports/${report.id}/view`, // Use API proxy for viewing
    size: report.size,
    filename: report.filename
  })) : null;

  // Reset to page 1 when filters change
  const handleFilterChange = (newReportType, newDateRange) => {
    if (newReportType !== reportType || newDateRange !== dateRange) {
      setPage(1)
    }
    if (newReportType !== reportType) setReportType(newReportType)
    if (newDateRange !== dateRange) setDateRange(newDateRange)
  }
  
  const displayReports = mappedReports || mockReports
  
  console.log('Reports data:', reports);
  console.log('Mapped reports:', mappedReports);
  console.log('Display reports:', displayReports);
  if (error) console.error('Reports query error:', error);

  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      // Force refresh the reports query
      await queryClient.invalidateQueries({ queryKey: ['reports'] })
      // Also refresh opportunities and matches in case new data affects reports
      await queryClient.invalidateQueries({ queryKey: ['opportunities'] })
      await queryClient.invalidateQueries({ queryKey: ['matches'] })
    } finally {
      setRefreshing(false)
    }
  }

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
        <div className="flex space-x-3">
          <button 
            onClick={handleRefresh}
            disabled={refreshing}
            className="btn btn-secondary disabled:opacity-50"
          >
            <RefreshCw className={`w-5 h-5 mr-2 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
          <button className="btn btn-primary">
            <FileText className="w-5 h-5 mr-2" />
            Generate New Report
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-4">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Reports</p>
              <p className="mt-2 text-3xl font-semibold text-gray-900">
                {totalReports || displayReports.length}
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
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <select
            value={reportType}
            onChange={(e) => handleFilterChange(e.target.value, dateRange)}
            className="input w-auto"
          >
            <option value="all">All Reports</option>
            <option value="web">Web Dashboards</option>
            <option value="user">User Reports</option>
            <option value="workflow">Manual Workflow Reports</option>
          </select>
          <select
            value={dateRange}
            onChange={(e) => handleFilterChange(reportType, e.target.value)}
            className="input w-auto"
          >
            <option value="7d">Last 7 Days</option>
            <option value="30d">Last 30 Days</option>
            <option value="90d">Last 90 Days</option>
            <option value="all">All Time</option>
          </select>
        </div>
        
        {/* Pagination Info */}
        {totalReports > 0 && (
          <div className="text-sm text-gray-500">
            Showing {(page - 1) * pageSize + 1}-{Math.min(page * pageSize, totalReports)} of {totalReports} reports
          </div>
        )}
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
            <ReportCard key={report.id} report={report} onViewReport={handleViewReport} />
          ))}
        </div>
      )}

      {/* Pagination Controls */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between border-t border-gray-200 bg-white px-4 py-3 sm:px-6">
          <div className="flex flex-1 justify-between sm:hidden">
            <button
              onClick={() => setPage(Math.max(1, page - 1))}
              disabled={page <= 1}
              className="relative inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(Math.min(totalPages, page + 1))}
              disabled={page >= totalPages}
              className="relative ml-3 inline-flex items-center rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
          <div className="hidden sm:flex sm:flex-1 sm:items-center sm:justify-between">
            <div>
              <p className="text-sm text-gray-700">
                Showing <span className="font-medium">{(page - 1) * pageSize + 1}</span> to{' '}
                <span className="font-medium">{Math.min(page * pageSize, totalReports)}</span> of{' '}
                <span className="font-medium">{totalReports}</span> results
              </p>
            </div>
            <div>
              <nav className="isolate inline-flex -space-x-px rounded-md shadow-sm" aria-label="Pagination">
                <button
                  onClick={() => setPage(Math.max(1, page - 1))}
                  disabled={page <= 1}
                  className="relative inline-flex items-center rounded-l-md px-2 py-2 text-gray-400 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="sr-only">Previous</span>
                  ←
                </button>
                
                {/* Page Numbers */}
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum
                  if (totalPages <= 5) {
                    pageNum = i + 1
                  } else if (page <= 3) {
                    pageNum = i + 1
                  } else if (page >= totalPages - 2) {
                    pageNum = totalPages - 4 + i
                  } else {
                    pageNum = page - 2 + i
                  }
                  
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setPage(pageNum)}
                      className={`relative inline-flex items-center px-4 py-2 text-sm font-semibold ${
                        pageNum === page
                          ? 'z-10 bg-primary-600 text-white focus:z-20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary-600'
                          : 'text-gray-900 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0'
                      }`}
                    >
                      {pageNum}
                    </button>
                  )
                })}
                
                <button
                  onClick={() => setPage(Math.min(totalPages, page + 1))}
                  disabled={page >= totalPages}
                  className="relative inline-flex items-center rounded-r-md px-2 py-2 text-gray-400 ring-1 ring-inset ring-gray-300 hover:bg-gray-50 focus:z-20 focus:outline-offset-0 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="sr-only">Next</span>
                  →
                </button>
              </nav>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
