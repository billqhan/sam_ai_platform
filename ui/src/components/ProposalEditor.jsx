import { useState, useEffect } from 'react'
import { proposalStorage } from '../services/proposalStorage'
import { 
  Save, 
  X, 
  FileText, 
  User, 
  DollarSign, 
  Calendar,
  CheckCircle,
  Clock,
  AlertCircle
} from 'lucide-react'

export default function ProposalEditor({ proposal, isOpen, onClose, onSave }) {
  const [formData, setFormData] = useState({
    title: '',
    opportunityId: '',
    agency: '',
    assignedTo: '',
    deadline: '',
    estimatedValue: '',
    status: 'draft',
    executiveSummary: '',
    technicalApproach: '',
    teamComposition: '',
    pricing: '',
    timeline: '',
    riskMitigation: ''
  })

  const [isSaving, setIsSaving] = useState(false)
  const [hasChanges, setHasChanges] = useState(false)

  useEffect(() => {
    if (proposal && isOpen) {
      setFormData({
        title: proposal.title || '',
        opportunityId: proposal.opportunityId || '',
        agency: proposal.agency || '',
        assignedTo: proposal.assignedTo || '',
        deadline: proposal.deadline || '',
        estimatedValue: proposal.estimatedValue || '',
        status: proposal.status || 'draft',
        executiveSummary: proposal.executiveSummary || '',
        technicalApproach: proposal.technicalApproach || '',
        teamComposition: proposal.teamComposition || '',
        pricing: proposal.pricing || '',
        timeline: proposal.timeline || '',
        riskMitigation: proposal.riskMitigation || ''
      })
      setHasChanges(false)
    }
  }, [proposal, isOpen])

  const handleInputChange = (field, value) => {
    setFormData(prev => ({
      ...prev,
      [field]: value
    }))
    setHasChanges(true)
  }

  const handleSave = async () => {
    setIsSaving(true)
    try {
      const updatedProposal = {
        ...proposal,
        ...formData,
        lastModified: new Date().toISOString().split('T')[0],
        progress: calculateProgress(formData)
      }

      // Save to storage with enhanced cloud integration
      const saveResults = await proposalStorage.saveProposal(updatedProposal)
      
      onSave(updatedProposal)
      setHasChanges(false)
      
      // Success feedback with storage details
      console.log('🎉 Proposal saved successfully!', saveResults)
      
      // Show detailed save status
      const storageStatus = []
      if (saveResults.localStorage) storageStatus.push('💾 Local')
      if (saveResults.cloudStorage) storageStatus.push('☁️ Cloud')
      
      const successMessage = `✅ "${updatedProposal.title}" saved to: ${storageStatus.join(', ')}`
      console.log(successMessage)
      
      if (saveResults.errors.length > 0) {
        console.warn('⚠️ Some storage errors occurred:', saveResults.errors)
      }
      
    } catch (error) {
      console.error('💥 Failed to save proposal:', error)
      alert(`❌ Failed to save proposal: ${error.message}\n\nPlease check your connection and try again.`)
    } finally {
      setIsSaving(false)
    }
  }

  const calculateProgress = (data) => {
    const sections = [
      data.executiveSummary,
      data.technicalApproach,
      data.teamComposition,
      data.pricing,
      data.timeline,
      data.riskMitigation
    ]
    
    const completedSections = sections.filter(section => 
      section && section.trim().length > 50
    ).length
    
    return Math.round((completedSections / sections.length) * 100)
  }

  const saveProposal = async (proposalData) => {
    console.log('💾 Saving proposal to storage...', proposalData.title)
    
    // 1. Save to localStorage first (immediate persistence)
    try {
      const existingProposals = JSON.parse(localStorage.getItem('proposals') || '[]')
      const updatedProposals = existingProposals.map(p => 
        p.id === proposalData.id ? proposalData : p
      )
      
      // If proposal doesn't exist, add it
      if (!existingProposals.find(p => p.id === proposalData.id)) {
        updatedProposals.push(proposalData)
      }
      
      localStorage.setItem('proposals', JSON.stringify(updatedProposals))
      console.log('✅ Saved to localStorage successfully')
    } catch (error) {
      console.error('❌ Failed to save to localStorage:', error)
      throw new Error('Failed to save locally')
    }

    // 2. Save to cloud storage (S3/DynamoDB integration)
    try {
      // For now, simulate API call - replace with actual API when backend is ready
      await simulateCloudSave(proposalData)
      console.log('☁️ Saved to cloud storage successfully')
    } catch (error) {
      console.warn('⚠️ Cloud save failed, but local save succeeded:', error.message)
      // Don't throw error here - local save succeeded, cloud is backup
    }
    
    return proposalData
  }

  // Simulate cloud storage save - replace with actual S3/DynamoDB calls
  const simulateCloudSave = async (proposalData) => {
    // Simulate network delay
    await new Promise(resolve => setTimeout(resolve, 500))
    
    // For demo purposes, save to a different localStorage key to simulate cloud
    const cloudKey = `proposals_cloud_${proposalData.id}`
    const cloudData = {
      ...proposalData,
      savedToCloud: true,
      cloudSaveTimestamp: new Date().toISOString(),
      version: (JSON.parse(localStorage.getItem(cloudKey) || '{}').version || 0) + 1
    }
    
    localStorage.setItem(cloudKey, JSON.stringify(cloudData))
    
    // TODO: Replace with actual cloud storage integration:
    // 
    // For S3 Document Storage:
    // const s3Response = await fetch('/api/proposals/upload-to-s3', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({
    //     proposalId: proposalData.id,
    //     content: proposalData,
    //     bucket: 'rfp-proposals-bucket',
    //     key: `proposals/${proposalData.id}/${Date.now()}.json`
    //   })
    // })
    //
    // For DynamoDB Structured Storage:
    // const dynamoResponse = await fetch('/api/proposals/save-to-dynamodb', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify({
    //     TableName: 'Proposals',
    //     Item: {
    //       proposalId: proposalData.id,
    //       title: proposalData.title,
    //       content: proposalData,
    //       lastModified: new Date().toISOString(),
    //       status: proposalData.status
    //     }
    //   })
    // })
    
    return cloudData
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'draft': return 'text-gray-600'
      case 'in_progress': return 'text-blue-600'
      case 'in_review': return 'text-yellow-600'
      case 'submitted': return 'text-green-600'
      default: return 'text-gray-600'
    }
  }

  const getStatusIcon = (status) => {
    switch (status) {
      case 'draft': return <FileText className="w-4 h-4" />
      case 'in_progress': return <Clock className="w-4 h-4" />
      case 'in_review': return <AlertCircle className="w-4 h-4" />
      case 'submitted': return <CheckCircle className="w-4 h-4" />
      default: return <FileText className="w-4 h-4" />
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-gray-500 bg-opacity-75" onClick={onClose}></div>
      
      <div className="fixed inset-0 overflow-hidden">
        <div className="absolute inset-0 overflow-hidden">
          <div className="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
            <div className="pointer-events-auto w-screen max-w-4xl">
              <div className="flex h-full flex-col overflow-y-scroll bg-white shadow-xl">
                
                {/* Header */}
                <div className="bg-primary-600 px-4 py-6 sm:px-6">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center">
                      <FileText className="h-6 w-6 text-white mr-3" />
                      <h2 className="text-lg font-medium text-white">
                        Edit Proposal: {formData.title}
                      </h2>
                    </div>
                    <div className="flex items-center space-x-2">
                      {hasChanges && (
                        <span className="text-yellow-200 text-sm">Unsaved changes</span>
                      )}
                      <button
                        onClick={handleSave}
                        disabled={isSaving || !hasChanges}
                        className="btn btn-sm bg-white text-primary-600 hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isSaving ? (
                          <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-primary-600 mr-2"></div>
                        ) : (
                          <Save className="w-4 h-4 mr-2" />
                        )}
                        {isSaving ? 'Saving...' : 'Save'}
                      </button>
                      <button
                        onClick={onClose}
                        className="text-white hover:text-gray-200"
                      >
                        <X className="h-6 w-6" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Content */}
                <div className="flex-1 px-4 py-6 sm:px-6">
                  <div className="space-y-6">
                    
                    {/* Basic Information */}
                    <div className="bg-gray-50 p-4 rounded-lg">
                      <h3 className="text-lg font-medium text-gray-900 mb-4">Basic Information</h3>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Proposal Title
                          </label>
                          <input
                            type="text"
                            value={formData.title}
                            onChange={(e) => handleInputChange('title', e.target.value)}
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Opportunity ID
                          </label>
                          <input
                            type="text"
                            value={formData.opportunityId}
                            onChange={(e) => handleInputChange('opportunityId', e.target.value)}
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Agency
                          </label>
                          <input
                            type="text"
                            value={formData.agency}
                            onChange={(e) => handleInputChange('agency', e.target.value)}
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Assigned To
                          </label>
                          <input
                            type="text"
                            value={formData.assignedTo}
                            onChange={(e) => handleInputChange('assignedTo', e.target.value)}
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Deadline
                          </label>
                          <input
                            type="date"
                            value={formData.deadline}
                            onChange={(e) => handleInputChange('deadline', e.target.value)}
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Estimated Value
                          </label>
                          <input
                            type="text"
                            value={formData.estimatedValue}
                            onChange={(e) => handleInputChange('estimatedValue', e.target.value)}
                            placeholder="$1,000,000"
                            className="input"
                          />
                        </div>
                        <div>
                          <label className="block text-sm font-medium text-gray-700 mb-1">
                            Status
                          </label>
                          <div className="relative">
                            <select
                              value={formData.status}
                              onChange={(e) => handleInputChange('status', e.target.value)}
                              className="input appearance-none"
                            >
                              <option value="draft">Draft</option>
                              <option value="in_progress">In Progress</option>
                              <option value="in_review">In Review</option>
                              <option value="submitted">Submitted</option>
                            </select>
                            <div className={`absolute left-3 top-1/2 transform -translate-y-1/2 ${getStatusColor(formData.status)}`}>
                              {getStatusIcon(formData.status)}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>

                    {/* Proposal Sections */}
                    <div className="space-y-6">
                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Executive Summary
                        </label>
                        <textarea
                          value={formData.executiveSummary}
                          onChange={(e) => handleInputChange('executiveSummary', e.target.value)}
                          rows={4}
                          placeholder="Provide a high-level overview of the proposed solution..."
                          className="textarea"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Technical Approach
                        </label>
                        <textarea
                          value={formData.technicalApproach}
                          onChange={(e) => handleInputChange('technicalApproach', e.target.value)}
                          rows={6}
                          placeholder="Detail the technical methodology, architecture, and implementation approach..."
                          className="textarea"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Team Composition
                        </label>
                        <textarea
                          value={formData.teamComposition}
                          onChange={(e) => handleInputChange('teamComposition', e.target.value)}
                          rows={4}
                          placeholder="Describe the team members, roles, and qualifications..."
                          className="textarea"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Pricing Structure
                        </label>
                        <textarea
                          value={formData.pricing}
                          onChange={(e) => handleInputChange('pricing', e.target.value)}
                          rows={4}
                          placeholder="Breakdown of costs, pricing model, and financial details..."
                          className="textarea"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Project Timeline
                        </label>
                        <textarea
                          value={formData.timeline}
                          onChange={(e) => handleInputChange('timeline', e.target.value)}
                          rows={4}
                          placeholder="Project phases, milestones, and delivery schedule..."
                          className="textarea"
                        />
                      </div>

                      <div>
                        <label className="block text-sm font-medium text-gray-700 mb-2">
                          Risk Mitigation
                        </label>
                        <textarea
                          value={formData.riskMitigation}
                          onChange={(e) => handleInputChange('riskMitigation', e.target.value)}
                          rows={4}
                          placeholder="Identified risks and mitigation strategies..."
                          className="textarea"
                        />
                      </div>
                    </div>

                    {/* Progress Indicator */}
                    <div className="bg-blue-50 p-4 rounded-lg">
                      <h4 className="text-sm font-medium text-blue-900 mb-2">
                        Completion Progress: {calculateProgress(formData)}%
                      </h4>
                      <div className="w-full bg-blue-200 rounded-full h-2">
                        <div 
                          className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${calculateProgress(formData)}%` }}
                        ></div>
                      </div>
                      <p className="text-xs text-blue-700 mt-1">
                        Complete each section with at least 50 characters for full progress
                      </p>
                    </div>
                  </div>
                </div>

                {/* Footer */}
                <div className="bg-gray-50 px-4 py-3 sm:px-6">
                  <div className="flex justify-between items-center">
                    <div className="text-sm text-gray-500 space-y-1">
                      <div>Last modified: {formData.lastModified || 'Never'}</div>
                      <div className="flex items-center space-x-2">
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                          💾 Local Storage
                        </span>
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-800">
                          ☁️ Cloud Ready
                        </span>
                      </div>
                    </div>
                    <div className="flex space-x-3">
                      <button
                        onClick={onClose}
                        className="btn-outline"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSave}
                        disabled={isSaving || !hasChanges}
                        className="btn disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {isSaving ? (
                          <>
                            <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                            Saving...
                          </>
                        ) : (
                          <>
                            <Save className="w-4 h-4 mr-2" />
                            Save Changes
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}