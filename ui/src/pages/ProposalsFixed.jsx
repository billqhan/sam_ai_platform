import { useState } from 'react'
import { 
  FileText, 
  Users, 
  Calendar, 
  DollarSign, 
  ExternalLink,
  Edit3,
  Send,
  Save,
  Eye,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Plus,
  Filter,
  Search
} from 'lucide-react'

// Mock data directly in component
const mockProposals = [
  {
    id: 1,
    opportunityId: 'W912DY-25-R-0001',
    title: 'IT Infrastructure Modernization Services',
    agency: 'Department of Defense',
    status: 'draft',
    assignedTo: 'Sarah Johnson',
    deadline: '2025-12-15',
    estimatedValue: '$2,500,000',
    createdAt: '2025-11-01',
    lastModified: '2025-11-03',
    progress: 35,
    sections: {
      executive: 'draft',
      technical: 'not_started',
      pricing: 'not_started',
      team: 'in_progress'
    }
  },
  {
    id: 2,
    opportunityId: 'N00014-25-R-0032',
    title: 'Advanced Analytics Platform Development',
    agency: 'Department of Navy',
    status: 'in_progress',
    assignedTo: 'Michael Chen',
    deadline: '2025-11-30',
    estimatedValue: '$1,800,000',
    createdAt: '2025-10-15',
    lastModified: '2025-11-02',
    progress: 68,
    sections: {
      executive: 'completed',
      technical: 'in_progress',
      pricing: 'draft',
      team: 'completed'
    }
  }
]

const mockMatches = [
  {
    id: '1',
    opportunityId: 'W912DY-25-R-0001',
    title: 'IT Infrastructure Modernization Services',
    agency: 'Department of Defense',
    type: 'Request for Proposal (RFP)',
    matchScore: 0.85,
    deadline: '2025-12-15',
    estimatedValue: '$2,500,000',
    description: 'Comprehensive IT infrastructure modernization including cloud migration.',
    keyRequirements: [
      'Security Clearance Required',
      'Cloud Architecture Experience'
    ],
    status: 'active'
  }
]

function ProposalCard({ proposal, onEdit, onView }) {
  const getStatusColor = (status) => {
    switch (status) {
      case 'draft': return 'bg-gray-100 text-gray-800'
      case 'in_progress': return 'bg-blue-100 text-blue-800'
      case 'in_review': return 'bg-yellow-100 text-yellow-800'
      case 'submitted': return 'bg-green-100 text-green-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 hover:shadow-md transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900 mb-1">{proposal.title}</h3>
          <p className="text-sm text-gray-600">{proposal.agency}</p>
          <p className="text-xs text-gray-500 mt-1">{proposal.opportunityId}</p>
        </div>
        <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(proposal.status)}`}>
          {proposal.status.replace('_', ' ')}
        </span>
      </div>

      <div className="space-y-3 mb-4">
        <div className="flex items-center text-sm text-gray-600">
          <Users className="w-4 h-4 mr-2" />
          Assigned to: {proposal.assignedTo}
        </div>
        <div className="flex items-center text-sm text-gray-600">
          <Calendar className="w-4 h-4 mr-2" />
          Deadline: {proposal.deadline}
        </div>
        <div className="flex items-center text-sm text-gray-600">
          <DollarSign className="w-4 h-4 mr-2" />
          Value: {proposal.estimatedValue}
        </div>
      </div>

      <div className="mb-4">
        <div className="flex justify-between text-sm text-gray-600 mb-1">
          <span>Progress</span>
          <span>{proposal.progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div 
            className="bg-primary-500 h-2 rounded-full transition-all duration-300"
            style={{ width: `${proposal.progress}%` }}
          ></div>
        </div>
      </div>

      <div className="flex gap-2">
        <button 
          onClick={() => onEdit(proposal)}
          className="btn btn-sm flex-1"
        >
          <Edit3 className="w-4 h-4 mr-1" />
          Edit
        </button>
        <button 
          onClick={() => onView(proposal)}
          className="btn-outline btn-sm flex-1"
        >
          <Eye className="w-4 h-4 mr-1" />
          View
        </button>
      </div>
    </div>
  )
}

export default function ProposalsFixed() {
  const [activeTab, setActiveTab] = useState('proposals')
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')

  console.log('ProposalsFixed rendering...')

  const proposals = mockProposals
  const matches = mockMatches

  const filteredProposals = proposals.filter(proposal => {
    const matchesSearch = proposal.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         proposal.agency.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         proposal.opportunityId.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || proposal.status === statusFilter
    return matchesSearch && matchesStatus
  })

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Contract Proposals</h1>
          <p className="mt-1 text-sm text-gray-500">
            Create and manage contract proposals based on opportunity matches
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-gray-200">
        <nav className="-mb-px flex space-x-8">
          <button
            onClick={() => setActiveTab('proposals')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'proposals'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Active Proposals ({proposals.length})
          </button>
          <button
            onClick={() => setActiveTab('opportunities')}
            className={`py-2 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'opportunities'
                ? 'border-primary-500 text-primary-600'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
            }`}
          >
            Available Opportunities ({matches.length})
          </button>
        </nav>
      </div>

      {/* Search */}
      <div className="flex flex-col sm:flex-row gap-4">
        <div className="flex-1">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400 w-4 h-4" />
            <input
              type="text"
              placeholder="Search by title, agency, or ID..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="input pl-10"
            />
          </div>
        </div>
        
        {activeTab === 'proposals' && (
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="input w-auto"
          >
            <option value="all">All Status</option>
            <option value="draft">Draft</option>
            <option value="in_progress">In Progress</option>
            <option value="in_review">In Review</option>
            <option value="submitted">Submitted</option>
          </select>
        )}
      </div>

      {/* Content */}
      {activeTab === 'proposals' && (
        <div>
          <p className="text-sm text-gray-500 mb-4">
            Showing {filteredProposals.length} of {proposals.length} proposals
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {filteredProposals.map(proposal => (
              <ProposalCard
                key={proposal.id}
                proposal={proposal}
                onEdit={(proposal) => console.log('Edit proposal:', proposal)}
                onView={(proposal) => console.log('View proposal:', proposal)}
              />
            ))}
            {filteredProposals.length === 0 && (
              <div className="col-span-full text-center py-12">
                <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 mb-2">No proposals found</h3>
                <p className="text-gray-500">
                  {searchTerm || statusFilter !== 'all' 
                    ? 'Try adjusting your search or filters'
                    : 'Start by creating a proposal from an opportunity match'
                  }
                </p>
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'opportunities' && (
        <div>
          <p className="text-sm text-gray-500 mb-4">
            Showing {matches.length} available opportunities
          </p>
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {matches.map(match => (
              <div key={match.id} className="bg-white rounded-lg border border-gray-200 p-6">
                <h3 className="text-lg font-semibold text-gray-900 mb-2">{match.title}</h3>
                <p className="text-sm text-gray-600 mb-2">{match.agency}</p>
                <p className="text-xs text-gray-500 mb-4">{match.opportunityId}</p>
                <div className="space-y-2">
                  <div className="flex items-center text-sm text-gray-600">
                    <Calendar className="w-4 h-4 mr-2" />
                    Deadline: {match.deadline}
                  </div>
                  <div className="flex items-center text-sm text-gray-600">
                    <DollarSign className="w-4 h-4 mr-2" />
                    Value: {match.estimatedValue}
                  </div>
                </div>
                <button className="btn btn-sm w-full mt-4">
                  Start Proposal
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}