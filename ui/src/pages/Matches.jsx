import { useState, useEffect } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { matchesApi } from '../services/api'
import {
  Target,
  TrendingUp,
  Calendar,
  Building2,
  FileText,
  ExternalLink,
  Star,
  Filter,
  Play,
  RefreshCw
} from 'lucide-react'
import { format, parseISO } from 'date-fns'

function MatchCard({ match }) {
  const scoreColor =
    match.score >= 0.9 ? 'text-success-600' :
    match.score >= 0.8 ? 'text-primary-600' :
    match.score >= 0.7 ? 'text-warning-600' : 'text-gray-600'

  const scoreBg =
    match.score >= 0.9 ? 'bg-success-50' :
    match.score >= 0.8 ? 'bg-primary-50' :
    match.score >= 0.7 ? 'bg-warning-50' : 'bg-gray-50'

  return (
    <div className="card hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <Link
            to={`/opportunities/${match.opportunityId}`}
            className="text-lg font-semibold text-gray-900 hover:text-primary-600"
          >
            {match.opportunityTitle}
          </Link>
          <div className="flex items-center mt-2 space-x-4 text-sm text-gray-500">
            <div className="flex items-center">
              <Building2 className="w-4 h-4 mr-1" />
              {match.agency}
            </div>
            <div className="flex items-center">
              <Calendar className="w-4 h-4 mr-1" />
              {format(parseISO(match.matchedDate), 'MMM dd, yyyy')}
            </div>
          </div>
        </div>
        <div className={`${scoreBg} px-4 py-2 rounded-lg text-center ml-4`}>
          <div className={`text-2xl font-bold ${scoreColor}`}>
            {(match.score * 100).toFixed(0)}%
          </div>
          <p className="text-xs text-gray-600 mt-1">Match Score</p>
        </div>
      </div>

      <p className="text-sm text-gray-600 mb-4 line-clamp-2">
        {match.description}
      </p>

      <div className="space-y-3 mb-4">
        <div>
          <h4 className="text-xs font-semibold text-gray-700 mb-1">Key Match Factors</h4>
          <div className="flex flex-wrap gap-1">
            {match.keyFactors?.slice(0, 3).map((factor, idx) => (
              <span key={idx} className="badge badge-info text-xs">
                {factor}
              </span>
            ))}
          </div>
        </div>
      </div>

      <div className="flex items-center justify-between pt-4 border-t border-gray-200">
        <div className="flex items-center space-x-3">
          {match.value && (
            <span className="text-sm font-medium text-gray-900">{match.value}</span>
          )}
          <span className="badge badge-success">
            {match.category}
          </span>
        </div>
        <div className="flex items-center space-x-2">
          <button className="p-2 text-gray-400 hover:text-warning-500 rounded-lg hover:bg-gray-100">
            <Star className="w-5 h-5" />
          </button>
          <Link
            to={`/opportunities/${match.opportunityId}`}
            className="p-2 text-gray-400 hover:text-primary-600 rounded-lg hover:bg-gray-100"
          >
            <ExternalLink className="w-5 h-5" />
          </Link>
        </div>
      </div>
    </div>
  )
}



export default function Matches() {
  const queryClient = useQueryClient()
  const [filter, setFilter] = useState('all') // all, high, medium
  const [sortBy, setSortBy] = useState('score') // score, date, value

  const { data: matches, isLoading, error } = useQuery({
    queryKey: ['matches', filter, sortBy],
    queryFn: () => matchesApi.getAll({ filter, sortBy }),
    select: (response) => {
      console.log('Matches API response:', response.data);
      const apiMatches = response.data?.items || response.data || [];
      
      // Map API response to expected UI format
      return apiMatches.map(match => ({
        id: match.id,
        opportunityId: match.opportunityId,
        opportunityTitle: match.title,
        description: `Match Score: ${(match.matchScore * 100).toFixed(0)}% - ${match.reason}`,
        agency: match.agency,
        category: match.type,
        matchedDate: match.createdDate,
        value: '$0',
        score: match.matchScore,
        keyFactors: [match.status, 'AI Match', 'Automated'],
      }));
    },
  })

  const triggerMatchingMutation = useMutation({
    mutationFn: () => matchesApi.triggerMatching(),
    onSuccess: (response) => {
      queryClient.invalidateQueries({ queryKey: ['matches'] })
      // Show success message
      console.log('Matching triggered successfully:', response.data)
    },
    onError: (error) => {
      console.error('Failed to trigger matching:', error)
    }
  })

  // Mock data
  const mockMatches = [
    {
      id: 'match-001',
      opportunityId: 'opp-001',
      opportunityTitle: 'Advanced Radar Systems Integration and Deployment',
      description: 'Integration and deployment of next-generation radar systems across multiple installations.',
      agency: 'US Air Force',
      category: 'Engineering',
      matchedDate: '2025-10-29T10:30:00Z',
      value: '$12.5M',
      score: 0.92,
      keyFactors: ['Radar Systems Expertise', 'DoD Experience', 'Security Clearance'],
    },
    {
      id: 'match-002',
      opportunityId: 'opp-002',
      opportunityTitle: 'Cybersecurity Infrastructure Modernization Program',
      description: 'DoD initiative to modernize cybersecurity infrastructure across all branches.',
      agency: 'Department of Defense',
      category: 'IT Services',
      matchedDate: '2025-10-28T11:15:00Z',
      value: '$8.3M',
      score: 0.89,
      keyFactors: ['Cybersecurity', 'Infrastructure', 'DoD Contracts'],
    },
    {
      id: 'match-003',
      opportunityId: 'opp-003',
      opportunityTitle: 'Satellite Communication Systems Development',
      description: 'Development of next-generation satellite communication systems for deep space missions.',
      agency: 'NASA',
      category: 'Research & Development',
      matchedDate: '2025-10-27T14:45:00Z',
      value: '$15.2M',
      score: 0.87,
      keyFactors: ['Satellite Systems', 'R&D Capability', 'Space Technology'],
    },
    {
      id: 'match-004',
      opportunityId: 'opp-004',
      opportunityTitle: 'Electronic Warfare Systems Upgrade',
      description: 'Comprehensive upgrade of electronic warfare systems for carrier battle groups.',
      agency: 'US Navy',
      category: 'Engineering',
      matchedDate: '2025-10-26T09:20:00Z',
      value: '$9.7M',
      score: 0.85,
      keyFactors: ['EW Systems', 'Naval Experience', 'System Integration'],
    },
    {
      id: 'match-005',
      opportunityId: 'opp-005',
      opportunityTitle: 'Command and Control Software Suite',
      description: 'Development of integrated command and control software for Army tactical operations.',
      agency: 'US Army',
      category: 'IT Services',
      matchedDate: '2025-10-25T13:30:00Z',
      value: '$6.1M',
      score: 0.83,
      keyFactors: ['C2 Systems', 'Software Development', 'Military IT'],
    },
  ]

  const displayMatches = matches && matches.length > 0 ? matches : mockMatches
  
  console.log('Matches data:', matches);
  console.log('Display matches:', displayMatches);
  if (error) console.error('Matches query error:', error);

  const filteredMatches = displayMatches.filter(match => {
    if (filter === 'high') return match.score >= 0.85
    if (filter === 'medium') return match.score >= 0.7 && match.score < 0.85
    return true
  })

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Matches</h1>
          <p className="mt-1 text-sm text-gray-500">
            AI-generated matches between opportunities and company capabilities
          </p>
        </div>
        <div className="flex items-center space-x-3">
          <button
            onClick={() => triggerMatchingMutation.mutate()}
            disabled={triggerMatchingMutation.isPending}
            className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {triggerMatchingMutation.isPending ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Generating...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Generate Matches
              </>
            )}
          </button>
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="input w-auto"
          >
            <option value="all">All Matches</option>
            <option value="high">High Quality (≥85%)</option>
            <option value="medium">Medium Quality (70-84%)</option>
          </select>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
            className="input w-auto"
          >
            <option value="score">Sort by Score</option>
            <option value="date">Sort by Date</option>
            <option value="value">Sort by Value</option>
          </select>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-3">
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Total Matches</p>
              <p className="mt-2 text-3xl font-semibold text-gray-900">
                {displayMatches.length}
              </p>
            </div>
            <Target className="w-12 h-12 text-primary-600 opacity-20" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">High Quality</p>
              <p className="mt-2 text-3xl font-semibold text-success-600">
                {displayMatches.filter(m => m.score >= 0.85).length}
              </p>
            </div>
            <TrendingUp className="w-12 h-12 text-success-600 opacity-20" />
          </div>
        </div>
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-600">Avg Score</p>
              <p className="mt-2 text-3xl font-semibold text-primary-600">
                {((displayMatches.reduce((sum, m) => sum + m.score, 0) / displayMatches.length) * 100).toFixed(0)}%
              </p>
            </div>
            <Star className="w-12 h-12 text-primary-600 opacity-20" />
          </div>
        </div>
      </div>

      {/* Matches List */}
      {isLoading ? (
        <div className="space-y-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="card animate-pulse">
              <div className="h-6 bg-gray-200 rounded w-3/4 mb-3"></div>
              <div className="h-4 bg-gray-200 rounded w-1/2 mb-4"></div>
              <div className="h-4 bg-gray-200 rounded w-full"></div>
            </div>
          ))}
        </div>
      ) : filteredMatches.length === 0 ? (
        <div className="card text-center py-12">
          <Target className="w-16 h-16 mx-auto text-gray-400 mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 mb-2">No matches found</h3>
          <p className="text-sm text-gray-500 mb-4">
            Click "Generate Matches" to analyze opportunities against company capabilities
          </p>
          <button
            onClick={() => triggerMatchingMutation.mutate()}
            disabled={triggerMatchingMutation.isPending}
            className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {triggerMatchingMutation.isPending ? (
              <>
                <RefreshCw className="w-4 h-4 mr-2 animate-spin" />
                Generating Matches...
              </>
            ) : (
              <>
                <Play className="w-4 h-4 mr-2" />
                Generate Matches
              </>
            )}
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {filteredMatches.map((match) => (
            <MatchCard key={match.id} match={match} />
          ))}
        </div>
      )}
    </div>
  )
}
