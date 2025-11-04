import { useState, useEffect } from 'react'
import ProposalEditor from '../components/ProposalEditor'
import { proposalStorage } from '../services/proposalStorage'
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

// Fallback mock data for when API is not available
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
    description: 'Comprehensive IT infrastructure modernization including cloud migration, cybersecurity enhancement, and system integration services.',
    keyRequirements: [
      'Security Clearance Required',
      'Cloud Architecture Experience',
      'DoD Standards Compliance',
      '24/7 Support Capability'
    ],
    status: 'active'
  },
  {
    id: '2',
    opportunityId: 'N00014-25-R-0032',
    title: 'Advanced Analytics Platform Development',
    agency: 'Department of Navy',
    type: 'Request for Proposal (RFP)',
    matchScore: 0.78,
    deadline: '2025-11-30',
    estimatedValue: '$1,800,000',
    description: 'Development of advanced analytics platform for maritime operations data analysis and predictive modeling.',
    keyRequirements: [
      'Machine Learning Expertise',
      'Maritime Domain Knowledge',
      'Real-time Processing',
      'Government Security Standards'
    ],
    status: 'active'
  },
  {
    id: '3',
    opportunityId: 'W15P7T-25-R-0089',
    title: 'Cybersecurity Assessment and Monitoring',
    agency: 'Department of Army',
    type: 'Request for Information (RFI)',
    matchScore: 0.72,
    deadline: '2025-11-20',
    estimatedValue: '$950,000',
    description: 'Comprehensive cybersecurity assessment and continuous monitoring services for military installations.',
    keyRequirements: [
      'NIST Compliance',
      'Penetration Testing',
      'Risk Assessment',
      'Continuous Monitoring'
    ],
    status: 'active'
  }
]

// Initial mock proposals - will be loaded from localStorage if available
const initialMockProposals = [
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
    executiveSummary: 'We propose a comprehensive IT infrastructure modernization solution that will enhance the Department of Defense\'s operational capabilities through cloud migration, advanced cybersecurity implementation, and seamless system integration.',
    technicalApproach: 'Our technical approach leverages industry-leading cloud platforms including AWS GovCloud and Azure Government, implementing zero-trust architecture principles with multi-factor authentication and continuous monitoring.',
    teamComposition: 'Project Manager: Sarah Johnson (PMP, Security+)\nLead Architect: David Smith (CISSP, AWS Certified)\nSecurity Specialist: Maria Rodriguez (CISM, CISSP)\nCloud Engineers: Team of 6 certified professionals',
    pricing: 'Phase 1: Infrastructure Assessment - $300,000\nPhase 2: Cloud Migration - $1,200,000\nPhase 3: Security Implementation - $800,000\nPhase 4: Integration & Testing - $200,000\nTotal: $2,500,000',
    timeline: 'Phase 1: 2 months - Infrastructure assessment and planning\nPhase 2: 6 months - Cloud platform setup and migration\nPhase 3: 4 months - Security framework implementation\nPhase 4: 2 months - Final integration and testing',
    riskMitigation: 'Security risks mitigated through continuous monitoring and compliance audits. Technical risks addressed via phased rollout with rollback capabilities. Schedule risks managed through dedicated project management and resource allocation.',
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
    status: 'in_review',
    assignedTo: 'Mike Chen',
    deadline: '2025-11-30',
    estimatedValue: '$1,800,000',
    createdAt: '2025-10-28',
    lastModified: '2025-11-02',
    progress: 85,
    executiveSummary: 'Our proposed Advanced Analytics Platform will revolutionize maritime operations through real-time data processing, predictive modeling, and AI-driven insights that enhance mission effectiveness and operational readiness.',
    technicalApproach: 'The platform utilizes cutting-edge machine learning algorithms, real-time streaming analytics with Apache Kafka, and scalable cloud infrastructure. We implement microservices architecture with containerized deployments using Kubernetes for optimal scalability.',
    teamComposition: 'Technical Lead: Mike Chen (PhD Computer Science, 15+ years maritime systems)\nML Engineers: Dr. Lisa Wang, Dr. James Park\nData Scientists: Team of 4 with maritime domain expertise\nDevOps Engineers: 3 certified Kubernetes specialists',
    pricing: 'Platform Development: $900,000\nML Model Training: $400,000\nIntegration & Testing: $300,000\nDeployment & Training: $200,000\nTotal: $1,800,000',
    timeline: 'Months 1-3: Requirements gathering and platform design\nMonths 4-8: Core development and ML model training\nMonths 9-11: Integration testing and optimization\nMonth 12: Deployment and user training',
    riskMitigation: 'Data quality risks addressed through robust validation pipelines. Performance risks mitigated via load testing and optimization. Integration risks managed through continuous testing and stakeholder feedback loops.',
    sections: {
      executive: 'completed',
      technical: 'completed',
      pricing: 'in_progress',
      team: 'completed'
    }
  }
]

function ProposalCard({ proposal, onEdit, onView }) {
  const getStatusColor = (status) => {
    const colors = {
      draft: 'bg-gray-100 text-gray-800',
      in_progress: 'bg-blue-100 text-blue-800',
      in_review: 'bg-yellow-100 text-yellow-800',
      submitted: 'bg-green-100 text-green-800',
      won: 'bg-emerald-100 text-emerald-800',
      lost: 'bg-red-100 text-red-800'
    }
    return colors[status] || colors.draft
  }

  const getSectionIcon = (status) => {
    switch(status) {
      case 'completed': return <CheckCircle className="w-4 h-4 text-green-600" />
      case 'in_progress': return <Clock className="w-4 h-4 text-blue-600" />
      case 'draft': return <Edit3 className="w-4 h-4 text-yellow-600" />
      default: return <XCircle className="w-4 h-4 text-gray-400" />
    }
  }

  return (
    <div className="card hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className="text-lg font-semibold text-gray-900 line-clamp-1">{proposal.title}</h3>
            <span className={`px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(proposal.status)}`}>
              {proposal.status.replace('_', ' ').toUpperCase()}
            </span>
          </div>
          <p className="text-sm text-gray-600 mb-2">{proposal.agency}</p>
          <p className="text-xs text-gray-500">ID: {proposal.opportunityId}</p>
        </div>
        <div className="flex space-x-2">
          <button
            onClick={() => onView(proposal)}
            className="btn btn-secondary btn-sm"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={() => onEdit(proposal)}
            className="btn btn-primary btn-sm"
          >
            <Edit3 className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-4 text-sm mb-4">
        <div>
          <p className="text-gray-500">Assigned to</p>
          <p className="font-medium">{proposal.assignedTo}</p>
        </div>
        <div>
          <p className="text-gray-500">Deadline</p>
          <p className="font-medium">{new Date(proposal.deadline).toLocaleDateString()}</p>
        </div>
        <div>
          <p className="text-gray-500">Est. Value</p>
          <p className="font-medium">{proposal.estimatedValue}</p>
        </div>
        <div>
          <p className="text-gray-500">Progress</p>
          <div className="flex items-center space-x-2">
            <div className="flex-1 bg-gray-200 rounded-full h-2">
              <div 
                className="bg-blue-600 h-2 rounded-full" 
                style={{ width: `${proposal.progress}%` }}
              ></div>
            </div>
            <span className="text-xs font-medium">{proposal.progress}%</span>
          </div>
        </div>
      </div>

      <div className="border-t pt-3">
        <p className="text-xs text-gray-500 mb-2">Proposal Sections</p>
        <div className="flex items-center justify-between text-xs">
          <div className="flex items-center space-x-1">
            {getSectionIcon(proposal.sections.executive)}
            <span>Executive</span>
          </div>
          <div className="flex items-center space-x-1">
            {getSectionIcon(proposal.sections.technical)}
            <span>Technical</span>
          </div>
          <div className="flex items-center space-x-1">
            {getSectionIcon(proposal.sections.pricing)}
            <span>Pricing</span>
          </div>
          <div className="flex items-center space-x-1">
            {getSectionIcon(proposal.sections.team)}
            <span>Team</span>
          </div>
        </div>
      </div>
    </div>
  )
}

function MatchCard({ match, onStartProposal }) {
  const getScoreColor = (score) => {
    if (score >= 0.8) return 'text-green-600 bg-green-50 border-green-200'
    if (score >= 0.6) return 'text-yellow-600 bg-yellow-50 border-yellow-200'
    return 'text-red-600 bg-red-50 border-red-200'
  }

  const daysUntilDeadline = Math.ceil((new Date(match.deadline) - new Date()) / (1000 * 60 * 60 * 24))

  return (
    <div className="card hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between mb-4">
        <div className="flex-1">
          <div className="flex items-center space-x-2 mb-2">
            <h3 className="text-lg font-semibold text-gray-900 line-clamp-1">{match.title}</h3>
            <div className={`px-2 py-1 rounded border text-xs font-medium ${getScoreColor(match.matchScore)}`}>
              {Math.round(match.matchScore * 100)}% match
            </div>
          </div>
          <p className="text-sm text-gray-600 mb-1">{match.agency}</p>
          <p className="text-xs text-gray-500">{match.opportunityId}</p>
        </div>
        <button
          onClick={() => onStartProposal(match)}
          className="btn btn-primary btn-sm"
        >
          <Plus className="w-4 h-4 mr-1" />
          Start Proposal
        </button>
      </div>

      <p className="text-sm text-gray-700 mb-4 line-clamp-2">{match.description}</p>

      <div className="grid grid-cols-2 gap-4 text-sm mb-4">
        <div>
          <p className="text-gray-500">Type</p>
          <p className="font-medium">{match.type}</p>
        </div>
        <div>
          <p className="text-gray-500">Est. Value</p>
          <p className="font-medium">{match.estimatedValue}</p>
        </div>
        <div>
          <p className="text-gray-500">Deadline</p>
          <div className="flex items-center space-x-1">
            <p className="font-medium">{new Date(match.deadline).toLocaleDateString()}</p>
            {daysUntilDeadline <= 7 && (
              <AlertCircle className="w-4 h-4 text-red-500" />
            )}
          </div>
          <p className="text-xs text-gray-500">{daysUntilDeadline} days remaining</p>
        </div>
      </div>

      <div className="border-t pt-3">
        <p className="text-xs text-gray-500 mb-2">Key Requirements</p>
        <div className="flex flex-wrap gap-1">
          {match.keyRequirements.slice(0, 3).map((req, index) => (
            <span key={index} className="px-2 py-1 bg-gray-100 text-gray-700 text-xs rounded">
              {req}
            </span>
          ))}
          {match.keyRequirements.length > 3 && (
            <span className="px-2 py-1 bg-gray-100 text-gray-500 text-xs rounded">
              +{match.keyRequirements.length - 3} more
            </span>
          )}
        </div>
      </div>
    </div>
  )
}

function NewProposalModal({ isOpen, onClose, opportunity, onSubmit }) {
  const [formData, setFormData] = useState({
    assignedTo: '',
    teamLead: '',
    estimatedHours: '',
    proposedValue: opportunity?.estimatedValue?.replace(/[$,]/g, '') || '',
    notes: ''
  })

  const handleSubmit = (e) => {
    e.preventDefault()
    onSubmit({
      opportunityId: opportunity.opportunityId,
      title: opportunity.title,
      agency: opportunity.agency,
      deadline: opportunity.deadline,
      estimatedValue: opportunity.estimatedValue,
      ...formData
    })
    onClose()
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50">
      <div className="bg-white rounded-lg max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h2 className="text-xl font-semibold text-gray-900">Create New Proposal</h2>
            <button onClick={onClose} className="text-gray-400 hover:text-gray-600">
              <XCircle className="w-6 h-6" />
            </button>
          </div>

          {opportunity && (
            <div className="bg-gray-50 p-4 rounded-lg mb-6">
              <h3 className="font-semibold text-gray-900 mb-2">{opportunity.title}</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-500">Agency:</span> {opportunity.agency}
                </div>
                <div>
                  <span className="text-gray-500">ID:</span> {opportunity.opportunityId}
                </div>
                <div>
                  <span className="text-gray-500">Deadline:</span> {new Date(opportunity.deadline).toLocaleDateString()}
                </div>
                <div>
                  <span className="text-gray-500">Est. Value:</span> {opportunity.estimatedValue}
                </div>
              </div>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Assigned To *
                </label>
                <select
                  value={formData.assignedTo}
                  onChange={(e) => setFormData({...formData, assignedTo: e.target.value})}
                  className="input"
                  required
                >
                  <option value="">Select team member</option>
                  <option value="Sarah Johnson">Sarah Johnson</option>
                  <option value="Mike Chen">Mike Chen</option>
                  <option value="Emily Rodriguez">Emily Rodriguez</option>
                  <option value="David Kim">David Kim</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Technical Lead
                </label>
                <select
                  value={formData.teamLead}
                  onChange={(e) => setFormData({...formData, teamLead: e.target.value})}
                  className="input"
                >
                  <option value="">Select tech lead</option>
                  <option value="Alex Thompson">Alex Thompson</option>
                  <option value="Lisa Park">Lisa Park</option>
                  <option value="James Wilson">James Wilson</option>
                </select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Estimated Hours
                </label>
                <input
                  type="number"
                  value={formData.estimatedHours}
                  onChange={(e) => setFormData({...formData, estimatedHours: e.target.value})}
                  className="input"
                  placeholder="e.g. 2000"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Proposed Value ($)
                </label>
                <input
                  type="number"
                  value={formData.proposedValue}
                  onChange={(e) => setFormData({...formData, proposedValue: e.target.value})}
                  className="input"
                  placeholder="e.g. 2500000"
                />
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Initial Notes
              </label>
              <textarea
                value={formData.notes}
                onChange={(e) => setFormData({...formData, notes: e.target.value})}
                className="input"
                rows="4"
                placeholder="Key strategies, initial thoughts, or important considerations..."
              />
            </div>

            <div className="flex justify-end space-x-3 pt-6 border-t">
              <button type="button" onClick={onClose} className="btn btn-secondary">
                Cancel
              </button>
              <button type="submit" className="btn btn-primary">
                Create Proposal
              </button>
            </div>
          </form>
        </div>
      </div>
    </div>
  )
}

export default function Proposals() {
  const [activeTab, setActiveTab] = useState('proposals')
  const [searchTerm, setSearchTerm] = useState('')
  const [statusFilter, setStatusFilter] = useState('all')
  const [showNewProposalModal, setShowNewProposalModal] = useState(false)
  const [selectedOpportunity, setSelectedOpportunity] = useState(null)
  
  // Proposal Editor State
  const [showProposalEditor, setShowProposalEditor] = useState(false)
  const [editingProposal, setEditingProposal] = useState(null)
  
  // Proposals state with localStorage persistence
  const [proposals, setProposals] = useState([])
  const [storageStatus, setStorageStatus] = useState({
    localStorage: true,
    cloudStorage: false,
    lastSync: 'Never',
    lastError: null
  })
  const proposalsLoading = false
  const proposalsError = null

  // Load proposals from storage on component mount
  useEffect(() => {
    const loadProposals = async () => {
      try {
        const loadedProposals = await proposalStorage.loadProposals()
        
        if (loadedProposals && loadedProposals.length > 0) {
          setProposals(loadedProposals)
          console.log('📥 Loaded existing proposals from storage')
          
          // Update storage status after successful load
          const status = await proposalStorage.getStorageStatus()
          setStorageStatus({
            ...status,
            lastSync: new Date().toLocaleString(),
            lastError: null
          })
        } else {
          // Initialize with mock data if no existing proposals
          setProposals(initialMockProposals)
          // Save initial mock data
          for (const proposal of initialMockProposals) {
            await proposalStorage.saveProposal(proposal)
          }
          console.log('🆕 Initialized with mock proposals')
          
          // Update storage status
          const status = await proposalStorage.getStorageStatus()
          setStorageStatus({
            ...status,
            lastSync: new Date().toLocaleString(),
            lastError: null
          })
        }
      } catch (error) {
        console.error('❌ Error loading proposals:', error)
        setProposals(initialMockProposals)
      }
    }

    loadProposals()
  }, [])

  // Use mock data directly for now to avoid React Query issues
  const matches = mockMatches
  const matchesLoading = false
  const matchesError = null

  // Editor handlers
  const handleEditProposal = (proposal) => {
    setEditingProposal(proposal)
    setShowProposalEditor(true)
  }

  const handleViewProposal = (proposal) => {
    // For now, viewing also opens the editor in read-only mode
    setEditingProposal(proposal)
    setShowProposalEditor(true)
  }

  const handleSaveProposal = async (updatedProposal) => {
    try {
      // Update local state
      const updatedProposals = proposals.map(p => 
        p.id === updatedProposal.id ? updatedProposal : p
      )
      
      setProposals(updatedProposals)
      
      // Save to storage systems
      const saveResults = await proposalStorage.saveProposal(updatedProposal)
      
      // Update storage status
      setStorageStatus({
        localStorage: saveResults.localStorage,
        cloudStorage: saveResults.cloudStorage,
        lastSync: new Date().toLocaleString(),
        lastError: saveResults.errors.length > 0 ? saveResults.errors.join(', ') : null
      })
      
      setShowProposalEditor(false)
      setEditingProposal(null)
      
      console.log('✅ Proposal saved successfully:', updatedProposal.title, saveResults)
      
    } catch (error) {
      console.error('❌ Failed to save proposal:', error)
      // Don't close editor if save failed
    }
  }

  const handleCloseEditor = () => {
    setShowProposalEditor(false)
    setEditingProposal(null)
  }

  const handleStartProposal = (opportunity) => {
    setSelectedOpportunity(opportunity)
    setShowNewProposalModal(true)
  }

  const handleCreateProposal = (proposalData) => {
    console.log('Creating proposal:', proposalData)
    // Mock proposal creation for now
    setShowNewProposalModal(false)
    setSelectedOpportunity(null)
  }

  const filteredProposals = proposals.filter(proposal => {
    const matchesSearch = proposal.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         proposal.agency.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         proposal.opportunityId.toLowerCase().includes(searchTerm.toLowerCase())
    const matchesStatus = statusFilter === 'all' || proposal.status === statusFilter
    return matchesSearch && matchesStatus
  })

  const filteredMatches = matches.filter(match => 
    match.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    match.agency.toLowerCase().includes(searchTerm.toLowerCase()) ||
    match.opportunityId.toLowerCase().includes(searchTerm.toLowerCase())
  )

  console.log('Proposals render:', {
    proposals: proposals.length,
    matches: matches.length,
    proposalsLoading,
    matchesLoading,
    proposalsError,
    matchesError
  })

  // Show loading state
  if (proposalsLoading || matchesLoading) {
    return (
      <div className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-500 mx-auto"></div>
            <p className="mt-4 text-gray-500">Loading proposals...</p>
          </div>
        </div>
      </div>
    )
  }

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
        
        {/* Storage Status Indicator */}
        <div className="flex items-center space-x-4">
          <div className="text-xs text-gray-500">
            <div className="flex items-center space-x-2">
              <span className="flex items-center space-x-1">
                <div className={`w-2 h-2 rounded-full ${storageStatus.localStorage ? 'bg-green-500' : 'bg-red-500'}`}></div>
                <span>Local</span>
              </span>
              <span className="flex items-center space-x-1">
                <div className={`w-2 h-2 rounded-full ${storageStatus.cloudStorage ? 'bg-green-500' : 'bg-yellow-500'}`}></div>
                <span>Cloud</span>
              </span>
            </div>
            <div className="text-right mt-1">
              Last sync: {storageStatus.lastSync}
            </div>
            {storageStatus.lastError && (
              <div className="text-red-500 text-right mt-1" title={storageStatus.lastError}>
                ⚠️ Error
              </div>
            )}
          </div>
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

      {/* Search and Filters */}
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
              onEdit={handleEditProposal}
              onView={handleViewProposal}
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
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredMatches.map(match => (
            <MatchCard
              key={match.id}
              match={match}
              onStartProposal={handleStartProposal}
            />
          ))}
          {filteredMatches.length === 0 && (
            <div className="col-span-full text-center py-12">
              <Target className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No opportunities found</h3>
              <p className="text-gray-500">
                {searchTerm 
                  ? 'Try adjusting your search terms'
                  : 'No matching opportunities available at this time'
                }
              </p>
            </div>
          )}
        </div>
      )}

      {/* New Proposal Modal */}
      <NewProposalModal
        isOpen={showNewProposalModal}
        onClose={() => {
          setShowNewProposalModal(false)
          setSelectedOpportunity(null)
        }}
        opportunity={selectedOpportunity}
        onSubmit={handleCreateProposal}
      />

      {/* Proposal Editor */}
      <ProposalEditor
        proposal={editingProposal}
        isOpen={showProposalEditor}
        onClose={handleCloseEditor}
        onSave={handleSaveProposal}
      />
    </div>
  )
}