import { useParams, Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { opportunitiesApi, matchesApi } from '../services/api'
import {
  ArrowLeft,
  Building2,
  Calendar,
  DollarSign,
  ExternalLink,
  FileText,
  Target,
  Clock,
  MapPin,
  Mail,
  Phone,
  User,
  Award
} from 'lucide-react'
import { format, parseISO, isValid } from 'date-fns'

export default function OpportunityDetail() {
  const { id } = useParams()

  const { data: opportunity, isLoading } = useQuery({
    queryKey: ['opportunity', id],
    queryFn: () => opportunitiesApi.getById(id),
    select: (response) => response.data,
  })

  const { data: matches } = useQuery({
    queryKey: ['matches', id],
    queryFn: async () => {
      try {
        const res = await matchesApi.getByOpportunity(id)
        return res
      } catch (err) {
        // Treat 404 as no matches; rethrow others
        if (err?.response?.status === 404) {
          return { data: { matches: [], total: 0 } }
        }
        throw err
      }
    },
    select: (response) => response.data,
  })

  // Mock data
  const mockOpportunity = {
    id: 'opp-001',
    title: 'Advanced Radar Systems Integration and Deployment',
    noticeId: 'W911S0-25-R-0042',
    description: 'The United States Air Force is seeking proposals for the integration and deployment of next-generation radar systems across multiple installations. This project encompasses comprehensive hardware procurement, custom software development, professional installation services, and ongoing maintenance support.\n\nThe selected contractor will be responsible for:\n- Design and integration of advanced radar systems\n- Installation at 12 Air Force bases across the continental United States\n- Custom software development for system integration\n- Training of Air Force personnel\n- 5-year maintenance and support contract\n\nThis is a critical modernization effort to enhance air defense capabilities and maintain technological superiority.',
    agency: 'US Air Force',
    office: 'Air Force Life Cycle Management Center',
    category: 'Engineering',
    naicsCode: '334511 - Search, Detection, and Navigation Instruments',
    setAsideType: 'Full and Open Competition',
    postedDate: '2025-10-29T08:00:00Z',
    responseDeadline: '2025-11-30T17:00:00Z',
    archiveDate: '2025-12-15T17:00:00Z',
    value: '$12.5M',
    placeOfPerformance: 'Various CONUS locations',
    contactName: 'John Smith',
    contactEmail: 'john.smith@us.af.mil',
    contactPhone: '(555) 123-4567',
    documents: [
      { name: 'Solicitation Document', url: '#', size: '2.4 MB' },
      { name: 'Statement of Work', url: '#', size: '1.8 MB' },
      { name: 'Technical Requirements', url: '#', size: '3.1 MB' },
    ],
    matchScore: 0.92,
    matchReason: 'Strong alignment with L3Harris radar systems expertise and previous DoD contracts',
  }

  const mockMatches = [
    {
      id: 'match-001',
      score: 0.92,
      companyProfile: 'L3Harris Technologies - Radar Systems Division',
      strengths: [
        'Extensive experience with military radar systems',
        'Previous successful Air Force contracts',
        'ISO 9001 certified manufacturing',
        'Security clearance infrastructure in place',
      ],
      opportunities: [
        'Expand presence in Air Force installations',
        'Leverage existing radar technology portfolio',
        'Potential for follow-on maintenance contracts',
      ],
      risks: [
        'Tight timeline for 12-site deployment',
        'Requires additional security clearances',
      ],
    },
  ]

  const displayOpp = opportunity || mockOpportunity
  const displayMatches = matches || mockMatches

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

  const formatPlaceOfPerformance = (pop) => {
    if (!pop) return 'N/A'
    if (typeof pop === 'string') return pop
    try {
      const city = pop?.city?.name || ''
      const state = pop?.state?.name || ''
      const country = pop?.country?.name || ''
      const zip = pop?.zip || ''
      const parts = [city, state, zip, country].filter(Boolean)
      return parts.length ? parts.join(', ') : 'N/A'
    } catch {
      return 'N/A'
    }
  }

  if (isLoading) {
    return (
      <div className="p-6">
        <div className="animate-pulse space-y-6">
          <div className="h-8 bg-gray-200 rounded w-1/4"></div>
          <div className="h-64 bg-gray-200 rounded"></div>
          <div className="h-48 bg-gray-200 rounded"></div>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 space-y-6">
      {/* Back Button */}
      <Link to="/opportunities" className="inline-flex items-center text-sm text-primary-600 hover:text-primary-700">
        <ArrowLeft className="w-4 h-4 mr-2" />
        Back to Opportunities
      </Link>

      {/* Header */}
      <div className="card">
        <div className="flex items-start justify-between mb-4">
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-gray-900">{displayOpp.title}</h1>
            <p className="mt-2 text-sm text-gray-500">Notice ID: {displayOpp.noticeId}</p>
          </div>
          {displayOpp.matchScore && (
            <div className="ml-4">
              <div className="text-right">
                <span className="text-3xl font-bold text-success-600">
                  {(displayOpp.matchScore * 100).toFixed(0)}%
                </span>
                <p className="text-sm text-gray-500">Match Score</p>
              </div>
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4 pt-4 border-t">
          <div className="flex items-center space-x-2">
            <Building2 className="w-5 h-5 text-gray-400" />
            <div>
              <p className="text-xs text-gray-500">Agency</p>
              <p className="text-sm font-medium text-gray-900">{displayOpp.agency}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Calendar className="w-5 h-5 text-gray-400" />
            <div>
              <p className="text-xs text-gray-500">Posted Date</p>
              <p className="text-sm font-medium text-gray-900">{safeFormat(displayOpp.postedDate)}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <Clock className="w-5 h-5 text-gray-400" />
            <div>
              <p className="text-xs text-gray-500">Response Deadline</p>
              <p className="text-sm font-medium text-danger-600">{safeFormat(displayOpp.responseDeadline)}</p>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <DollarSign className="w-5 h-5 text-gray-400" />
            <div>
              <p className="text-xs text-gray-500">Contract Value</p>
              <p className="text-sm font-medium text-gray-900">{displayOpp.value}</p>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Main Content */}
        <div className="lg:col-span-2 space-y-6">
          {/* Description */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Description</h2>
            <div className="prose prose-sm max-w-none text-gray-600 whitespace-pre-line">
              {displayOpp.description}
            </div>
          </div>

          {/* Match Analysis */}
          {displayMatches.length > 0 && (
            <div className="card">
              <h2 className="text-lg font-semibold text-gray-900 mb-4">AI Match Analysis</h2>
              {displayMatches.map((match) => (
                <div key={match.id} className="space-y-4">
                  <div>
                    <h3 className="text-sm font-semibold text-gray-700 mb-2">Company Profile</h3>
                    <p className="text-sm text-gray-600">{match.companyProfile}</p>
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold text-success-700 mb-2">
                      <Award className="w-4 h-4 inline mr-1" />
                      Strengths
                    </h3>
                    <ul className="list-disc list-inside space-y-1">
                      {match.strengths.map((strength, idx) => (
                        <li key={idx} className="text-sm text-gray-600">{strength}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold text-primary-700 mb-2">
                      <Target className="w-4 h-4 inline mr-1" />
                      Opportunities
                    </h3>
                    <ul className="list-disc list-inside space-y-1">
                      {match.opportunities.map((opp, idx) => (
                        <li key={idx} className="text-sm text-gray-600">{opp}</li>
                      ))}
                    </ul>
                  </div>

                  <div>
                    <h3 className="text-sm font-semibold text-warning-700 mb-2">
                      <Clock className="w-4 h-4 inline mr-1" />
                      Risks & Considerations
                    </h3>
                    <ul className="list-disc list-inside space-y-1">
                      {match.risks.map((risk, idx) => (
                        <li key={idx} className="text-sm text-gray-600">{risk}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Documents */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Documents</h2>
            <div className="space-y-2">
              {displayOpp.documents?.map((doc, idx) => (
                <a
                  key={idx}
                  href={doc.url}
                  className="flex items-center justify-between p-3 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors"
                >
                  <div className="flex items-center space-x-3">
                    <FileText className="w-5 h-5 text-primary-600" />
                    <div>
                      <p className="text-sm font-medium text-gray-900">{doc.name}</p>
                      <p className="text-xs text-gray-500">{doc.size}</p>
                    </div>
                  </div>
                  <ExternalLink className="w-4 h-4 text-gray-400" />
                </a>
              ))}
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Details */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Details</h2>
            <div className="space-y-3">
              <div>
                <p className="text-xs text-gray-500 mb-1">Office</p>
                <p className="text-sm text-gray-900">{displayOpp.office}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Category</p>
                <span className="badge badge-info">{displayOpp.category}</span>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">NAICS Code</p>
                <p className="text-sm text-gray-900">{displayOpp.naicsCode}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 mb-1">Set-Aside Type</p>
                <p className="text-sm text-gray-900">{displayOpp.setAsideType}</p>
              </div>
              <div className="flex items-start space-x-2 pt-3 border-t">
                <MapPin className="w-4 h-4 text-gray-400 mt-0.5" />
                <div>
                  <p className="text-xs text-gray-500 mb-1">Place of Performance</p>
                  <p className="text-sm text-gray-900">{formatPlaceOfPerformance(displayOpp.placeOfPerformance)}</p>
                </div>
              </div>
            </div>
          </div>

          {/* Contact */}
          <div className="card">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Point of Contact</h2>
            <div className="space-y-3">
              <div className="flex items-center space-x-2">
                <User className="w-4 h-4 text-gray-400" />
                <p className="text-sm text-gray-900">{displayOpp.contactName}</p>
              </div>
              <div className="flex items-center space-x-2">
                <Mail className="w-4 h-4 text-gray-400" />
                <a href={`mailto:${displayOpp.contactEmail}`} className="text-sm text-primary-600 hover:text-primary-700">
                  {displayOpp.contactEmail}
                </a>
              </div>
              <div className="flex items-center space-x-2">
                <Phone className="w-4 h-4 text-gray-400" />
                <a href={`tel:${displayOpp.contactPhone}`} className="text-sm text-primary-600 hover:text-primary-700">
                  {displayOpp.contactPhone}
                </a>
              </div>
            </div>
          </div>

          {/* Actions */}
          <div className="card space-y-2">
            <Link to={`/matches?opportunity=${id}`} className="w-full btn btn-primary">
              <Target className="w-4 h-4 mr-2" />
              View Match Details
            </Link>
            <a
              href={`https://sam.gov/opp/${displayOpp.noticeId}`}
              target="_blank"
              rel="noopener noreferrer"
              className="w-full btn btn-secondary"
            >
              <ExternalLink className="w-4 h-4 mr-2" />
              View on SAM.gov
            </a>
          </div>
        </div>
      </div>
    </div>
  )
}
