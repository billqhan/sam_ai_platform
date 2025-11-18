import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { opportunitiesApi } from '../services/api'
import {
  Search,
  Filter,
  Calendar,
  Building2,
  DollarSign,
  ExternalLink,
  ChevronDown,
  X
} from 'lucide-react'
import { format, parseISO, isValid } from 'date-fns'

function FilterPanel({ filters, onFilterChange, onClearFilters }) {
  const [showFilters, setShowFilters] = useState(false)

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center space-x-2">
          <Filter className="w-5 h-5 text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900">Filters</h3>
        </div>
        <button
          onClick={() => setShowFilters(!showFilters)}
          className="lg:hidden btn btn-secondary"
        >
          {showFilters ? 'Hide' : 'Show'}
          <ChevronDown className={`w-4 h-4 ml-2 transition-transform ${showFilters ? 'rotate-180' : ''}`} />
        </button>
      </div>

      <div className={`space-y-4 ${showFilters ? 'block' : 'hidden lg:block'}`}>
        {/* Date Range */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Date Range
          </label>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="date"
              value={filters.dateFrom || ''}
              onChange={(e) => onFilterChange('dateFrom', e.target.value)}
              className="input text-sm"
            />
            <input
              type="date"
              value={filters.dateTo || ''}
              onChange={(e) => onFilterChange('dateTo', e.target.value)}
              className="input text-sm"
            />
          </div>
        </div>

        {/* Category */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Category
          </label>
          <select
            value={filters.category || ''}
            onChange={(e) => onFilterChange('category', e.target.value)}
            className="input"
          >
            <option value="">All Categories</option>
            <option value="it">IT Services</option>
            <option value="engineering">Engineering</option>
            <option value="consulting">Consulting</option>
            <option value="manufacturing">Manufacturing</option>
            <option value="research">Research & Development</option>
          </select>
        </div>

        {/* Agency */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Agency
          </label>
          <select
            value={filters.agency || ''}
            onChange={(e) => onFilterChange('agency', e.target.value)}
            className="input"
          >
            <option value="">All Agencies</option>
            <option value="dod">Department of Defense</option>
            <option value="airforce">US Air Force</option>
            <option value="navy">US Navy</option>
            <option value="army">US Army</option>
            <option value="nasa">NASA</option>
            <option value="dhs">Department of Homeland Security</option>
          </select>
        </div>

        {/* Value Range */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Contract Value
          </label>
          <div className="grid grid-cols-2 gap-2">
            <input
              type="number"
              placeholder="Min"
              value={filters.valueMin || ''}
              onChange={(e) => onFilterChange('valueMin', e.target.value)}
              className="input text-sm"
            />
            <input
              type="number"
              placeholder="Max"
              value={filters.valueMax || ''}
              onChange={(e) => onFilterChange('valueMax', e.target.value)}
              className="input text-sm"
            />
          </div>
        </div>

        {/* Match Status */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Match Status
          </label>
          <select
            value={filters.matchStatus || ''}
            onChange={(e) => onFilterChange('matchStatus', e.target.value)}
            className="input"
          >
            <option value="">All Opportunities</option>
            <option value="matched">Has Matches</option>
            <option value="high">High Quality Matches</option>
            <option value="no_match">No Matches</option>
          </select>
        </div>

        {/* Clear Filters */}
        <button
          onClick={onClearFilters}
          className="w-full btn btn-secondary"
        >
          <X className="w-4 h-4 mr-2" />
          Clear All Filters
        </button>
      </div>
    </div>
  )
}

function OpportunityCard({ opportunity }) {
  const matchScore = opportunity.matchScore || 0
  const hasMatch = matchScore > 0.7

  const safeFormat = (dateStr, fmt = 'MMM dd, yyyy') => {
    if (!dateStr) return 'N/A'
    try {
      const d = parseISO(dateStr)
      if (!isValid(d)) return 'N/A'
      return format(d, fmt)
    } catch {
      return 'N/A'
    }
  }

  return (
    <Link
      to={`/opportunities/${opportunity.id}`}
      className="card hover:shadow-lg transition-shadow cursor-pointer"
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 hover:text-primary-600">
            {opportunity.title}
          </h3>
          <div className="flex items-center mt-2 space-x-4 text-sm text-gray-500">
            <div className="flex items-center">
              <Building2 className="w-4 h-4 mr-1" />
              {opportunity.agency}
            </div>
            <div className="flex items-center">
              <Calendar className="w-4 h-4 mr-1" />
              {safeFormat(opportunity.postedDate)}
            </div>
          </div>
        </div>
        {hasMatch && (
          <span className="badge badge-success ml-4">
            Match: {(matchScore * 100).toFixed(0)}%
          </span>
        )}
      </div>

      <p className="text-sm text-gray-600 mb-4 line-clamp-2">
        {opportunity.description}
      </p>

      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <div className="flex items-center space-x-4">
          {opportunity.value && (
            <div className="flex items-center text-sm font-medium text-gray-900">
              <DollarSign className="w-4 h-4 mr-1 text-success-600" />
              {opportunity.value}
            </div>
          )}
          <span className="badge badge-info">
            {opportunity.category}
          </span>
        </div>
        <ExternalLink className="w-4 h-4 text-gray-400" />
      </div>
    </Link>
  )
}

export default function Opportunities() {
  const [searchQuery, setSearchQuery] = useState('')
  const [filters, setFilters] = useState({})
  const [page, setPage] = useState(1)
  const pageSize = 20

  const { data: opportunities, isLoading } = useQuery({
    queryKey: ['opportunities', searchQuery, filters, page],
    queryFn: () => opportunitiesApi.getAll({ 
      search: searchQuery, 
      ...filters, 
      page, 
      pageSize 
    }),
    select: (response) => response.data,
  })

  const handleFilterChange = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }))
    setPage(1) // Reset to first page
  }

  const handleClearFilters = () => {
    setFilters({})
    setPage(1)
  }

  const handleSearch = (e) => {
    setSearchQuery(e.target.value)
    setPage(1)
  }

  // Mock data for demo
  const mockOpportunities = {
    total: 1247,
    items: [
      {
        id: 'opp-001',
        title: 'Advanced Radar Systems Integration and Deployment',
        description: 'The United States Air Force is seeking proposals for the integration and deployment of next-generation radar systems across multiple installations. This includes hardware procurement, software development, installation, and ongoing maintenance.',
        agency: 'US Air Force',
        category: 'Engineering',
        postedDate: '2025-10-29T08:00:00Z',
        responseDeadline: '2025-11-30T17:00:00Z',
        value: '$12.5M',
        matchScore: 0.92,
      },
      {
        id: 'opp-002',
        title: 'Cybersecurity Infrastructure Modernization Program',
        description: 'Department of Defense initiative to modernize cybersecurity infrastructure across all branches. Requires expertise in network security, threat detection, and incident response systems.',
        agency: 'Department of Defense',
        category: 'IT Services',
        postedDate: '2025-10-28T10:30:00Z',
        responseDeadline: '2025-12-15T17:00:00Z',
        value: '$8.3M',
        matchScore: 0.89,
      },
      {
        id: 'opp-003',
        title: 'Satellite Communication Systems Development',
        description: 'NASA seeks contractor for development of next-generation satellite communication systems for deep space missions. Includes design, prototyping, testing, and deployment support.',
        agency: 'NASA',
        category: 'Research & Development',
        postedDate: '2025-10-27T14:20:00Z',
        responseDeadline: '2025-11-25T17:00:00Z',
        value: '$15.2M',
        matchScore: 0.87,
      },
      {
        id: 'opp-004',
        title: 'Electronic Warfare Systems Upgrade',
        description: 'US Navy requires comprehensive upgrade of electronic warfare systems for carrier battle groups. Scope includes hardware replacement, software modernization, and crew training.',
        agency: 'US Navy',
        category: 'Engineering',
        postedDate: '2025-10-26T09:15:00Z',
        responseDeadline: '2025-12-01T17:00:00Z',
        value: '$9.7M',
        matchScore: 0.85,
      },
      {
        id: 'opp-005',
        title: 'Command and Control Software Suite',
        description: 'Development of integrated command and control software for Army tactical operations. Must support real-time data processing, secure communications, and mobile deployment.',
        agency: 'US Army',
        category: 'IT Services',
        postedDate: '2025-10-25T11:45:00Z',
        responseDeadline: '2025-11-20T17:00:00Z',
        value: '$6.1M',
        matchScore: 0.83,
      },
      {
        id: 'opp-006',
        title: 'Unmanned Aerial Systems Maintenance Services',
        description: 'Comprehensive maintenance and support services for unmanned aerial systems fleet. Includes preventive maintenance, repairs, and logistics support.',
        agency: 'US Air Force',
        category: 'Manufacturing',
        postedDate: '2025-10-24T13:00:00Z',
        responseDeadline: '2025-12-10T17:00:00Z',
        value: '$4.8M',
        matchScore: 0.78,
      },
      {
        id: 'opp-007',
        title: 'Border Security Sensor Network Implementation',
        description: 'Design and deployment of advanced sensor network for border security operations. Requires integration with existing systems and 24/7 monitoring capabilities.',
        agency: 'Department of Homeland Security',
        category: 'IT Services',
        postedDate: '2025-10-23T15:30:00Z',
        responseDeadline: '2025-11-28T17:00:00Z',
        value: '$11.2M',
        matchScore: 0.76,
      },
      {
        id: 'opp-008',
        title: 'Military Training Simulation Systems',
        description: 'Development of immersive training simulation systems for military personnel. Includes VR/AR technology, scenario development, and performance analytics.',
        agency: 'Department of Defense',
        category: 'IT Services',
        postedDate: '2025-10-22T08:45:00Z',
        responseDeadline: '2025-12-05T17:00:00Z',
        value: '$7.5M',
        matchScore: 0.72,
      },
    ],
  }

  const displayData = opportunities || mockOpportunities

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Opportunities</h1>
        <p className="mt-1 text-sm text-gray-500">
          Browse and search contract opportunities from SAM.gov
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
        {/* Filters Sidebar */}
        <div className="lg:col-span-1">
          <FilterPanel
            filters={filters}
            onFilterChange={handleFilterChange}
            onClearFilters={handleClearFilters}
          />
        </div>

        {/* Main Content */}
        <div className="lg:col-span-3 space-y-6">
          {/* Search Bar */}
          <div className="card">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-5 h-5 text-gray-400" />
              <input
                type="text"
                placeholder="Search opportunities by title, description, or ID..."
                value={searchQuery}
                onChange={handleSearch}
                className="w-full pl-10 pr-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
              />
            </div>
          </div>

          {/* Results Header */}
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-600">
              {isLoading ? (
                'Loading...'
              ) : (
                <>
                  Showing <span className="font-medium">{displayData.items?.length || 0}</span> of{' '}
                  <span className="font-medium">{displayData.total || 0}</span> opportunities
                </>
              )}
            </p>
            <select className="input w-auto text-sm">
              <option>Sort by: Relevance</option>
              <option>Sort by: Date (Newest)</option>
              <option>Sort by: Date (Oldest)</option>
              <option>Sort by: Match Score</option>
              <option>Sort by: Value (High to Low)</option>
            </select>
          </div>

          {/* Opportunity List */}
          {isLoading ? (
            <div className="space-y-4">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="card animate-pulse">
                  <div className="h-6 bg-gray-200 rounded w-3/4 mb-3"></div>
                  <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
                  <div className="h-4 bg-gray-200 rounded w-full mb-2"></div>
                  <div className="h-4 bg-gray-200 rounded w-5/6"></div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              {displayData.items?.map((opportunity) => (
                <OpportunityCard key={opportunity.id} opportunity={opportunity} />
              ))}
            </div>
          )}

          {/* Pagination */}
          <div className="flex items-center justify-between card">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-sm text-gray-600">
              Page {page} of {Math.ceil((displayData.total || 0) / pageSize)}
            </span>
            <button
              onClick={() => setPage(p => p + 1)}
              disabled={page >= Math.ceil((displayData.total || 0) / pageSize)}
              className="btn btn-secondary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
