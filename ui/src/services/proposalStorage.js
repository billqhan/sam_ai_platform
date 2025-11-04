// Storage service for proposals - supports localStorage, S3, and DynamoDB
import { storageConfig } from '../config/storage.js'

class ProposalStorageService {
  constructor() {
    this.localStorageKey = 'proposals'
    this.cloudStorageEnabled = storageConfig.preferences.enableCloudStorage
    this.config = storageConfig
  }

  // Save proposal to all available storage systems
  async saveProposal(proposal) {
    console.log('📝 Saving proposal:', proposal.title)
    
    const results = {
      localStorage: false,
      cloudStorage: false,
      errors: []
    }

    // 1. Save to localStorage (immediate persistence)
    try {
      await this.saveToLocalStorage(proposal)
      results.localStorage = true
      console.log('✅ Saved to localStorage')
    } catch (error) {
      results.errors.push(`localStorage: ${error.message}`)
      console.error('❌ localStorage save failed:', error)
    }

    // 2. Save to cloud storage if enabled
    if (this.cloudStorageEnabled) {
      try {
        await this.saveToCloudStorage(proposal)
        results.cloudStorage = true
        console.log('☁️ Saved to cloud storage')
      } catch (error) {
        results.errors.push(`cloudStorage: ${error.message}`)
        console.warn('⚠️ Cloud storage save failed:', error)
      }
    } else {
      console.log('⏭️ Cloud storage disabled - skipping')
    }

    return results
  }

  // Load proposals from storage
  async loadProposals() {
    try {
      // Try cloud storage first if enabled
      if (this.cloudStorageEnabled) {
        try {
          const cloudProposals = await this.loadFromCloudStorage()
          if (cloudProposals && cloudProposals.length > 0) {
            console.log('📥 Loaded proposals from cloud storage')
            return cloudProposals
          }
        } catch (error) {
          console.warn('⚠️ Failed to load from cloud, falling back to localStorage:', error)
        }
      }

      // Fallback to localStorage
      const localProposals = await this.loadFromLocalStorage()
      console.log('📥 Loaded proposals from localStorage')
      return localProposals

    } catch (error) {
      console.error('❌ Failed to load proposals:', error)
      return []
    }
  }

  // localStorage operations
  async saveToLocalStorage(proposal) {
    const existingProposals = this.loadFromLocalStorageSync()
    const updatedProposals = existingProposals.map(p => 
      p.id === proposal.id ? proposal : p
    )
    
    // If proposal doesn't exist, add it
    if (!existingProposals.find(p => p.id === proposal.id)) {
      updatedProposals.push(proposal)
    }
    
    localStorage.setItem(this.localStorageKey, JSON.stringify(updatedProposals))
    return proposal
  }

  async loadFromLocalStorage() {
    return this.loadFromLocalStorageSync()
  }

  loadFromLocalStorageSync() {
    try {
      const stored = localStorage.getItem(this.localStorageKey)
      return stored ? JSON.parse(stored) : []
    } catch (error) {
      console.error('Failed to parse localStorage proposals:', error)
      return []
    }
  }

  // Cloud storage operations (DynamoDB via Lambda)
  async saveToCloudStorage(proposal) {
    console.log('☁️ Attempting to save to DynamoDB via Lambda:', proposal.id)
    
    try {
      // Call our Lambda function via API
      const response = await this.invokeLambdaFunction('POST', '/proposals', {
        proposal: {
          proposalId: proposal.id,
          title: proposal.title,
          agency: proposal.agency,
          rfpNumber: proposal.rfpNumber,
          deadline: proposal.deadline,
          status: proposal.status || 'draft',
          assignedTo: proposal.assignedTo || 'unassigned',
          content: JSON.stringify(proposal),
          lastModified: new Date().toISOString(),
          searchableText: `${proposal.title} ${proposal.agency} ${proposal.executiveSummary || ''}`.toLowerCase()
        }
      })

      if (response.success) {
        console.log('✅ Successfully saved to DynamoDB:', response.data)
        return proposal
      } else {
        throw new Error(`DynamoDB save failed: ${response.error}`)
      }
    } catch (error) {
      console.error('❌ DynamoDB save failed:', error)
      
      // Fallback to localStorage cloud backup for now
      const cloudKey = `proposals_cloud_backup`
      const allCloudProposals = JSON.parse(localStorage.getItem(cloudKey) || '[]')
      const updatedCloudProposals = allCloudProposals.map(p => 
        p.id === proposal.id ? { ...proposal, cloudSaved: false, cloudError: error.message } : p
      )
      
      if (!allCloudProposals.find(p => p.id === proposal.id)) {
        updatedCloudProposals.push({ ...proposal, cloudSaved: false, cloudError: error.message })
      }
      
      localStorage.setItem(cloudKey, JSON.stringify(updatedCloudProposals))
      throw error
    }
  }

  async loadFromCloudStorage() {
    console.log('☁️ Loading proposals from DynamoDB via Lambda')
    
    try {
      const response = await this.invokeLambdaFunction('GET', '/proposals')
      
      if (response.success && response.data) {
        console.log('✅ Successfully loaded from DynamoDB:', response.data.length, 'proposals')
        return response.data.map(item => {
          // Parse the stored content back to proposal object
          const proposal = JSON.parse(item.content || '{}')
          return {
            ...proposal,
            id: item.proposalId,
            lastModified: item.lastModified,
            cloudSaved: true
          }
        })
      } else {
        throw new Error(`DynamoDB load failed: ${response.error}`)
      }
    } catch (error) {
      console.error('❌ DynamoDB load failed, falling back to localStorage:', error)
      
      // Fallback to localStorage cloud backup
      const cloudKey = `proposals_cloud_backup`
      const cloudProposals = localStorage.getItem(cloudKey)
      return cloudProposals ? JSON.parse(cloudProposals) : []
    }
  }

  // Lambda function invocation
  async invokeLambdaFunction(method, path, body = null) {
    console.log(`🚀 Invoking Lambda: ${method} ${path}`)
    
    // For now, we'll simulate the Lambda response since we need API Gateway
    // TODO: Replace with actual API Gateway endpoint when available
    if (this.config.lambda.useDirectInvocation) {
      return this.simulateLambdaResponse(method, path, body)
    }
    
    // Future API Gateway implementation:
    // const response = await fetch(`${this.config.lambda.apiGatewayUrl}${path}`, {
    //   method,
    //   headers: {
    //     'Content-Type': 'application/json',
    //   },
    //   body: body ? JSON.stringify(body) : null
    // })
    // return response.json()
  }

  // Simulate Lambda responses for testing (remove when API Gateway is ready)
  async simulateLambdaResponse(method, path, body) {
    await this.simulateNetworkDelay()
    
    if (method === 'GET' && path === '/proposals') {
      // Return empty array for now - will be replaced with actual DynamoDB data
      return {
        success: true,
        data: [],
        message: 'No proposals found (simulation)'
      }
    }
    
    if (method === 'POST' && path === '/proposals') {
      // Simulate successful save
      return {
        success: true,
        data: {
          proposalId: body.proposal.proposalId,
          status: 'saved'
        },
        message: 'Proposal saved successfully (simulation)'
      }
    }
    
    return {
      success: false,
      error: 'Method not implemented in simulation'
    }
  }

  // Utility functions
  async simulateNetworkDelay() {
    await new Promise(resolve => setTimeout(resolve, 300 + Math.random() * 500))
  }

  // Enable cloud storage when backend is ready
  enableCloudStorage() {
    this.cloudStorageEnabled = true
    console.log('☁️ Cloud storage enabled')
  }

  disableCloudStorage() {
    this.cloudStorageEnabled = false
    console.log('💾 Using localStorage only')
  }

  // Get storage status
  async getStorageStatus() {
    return {
      localStorage: true,
      cloudStorage: this.cloudStorageEnabled,
      lastSync: localStorage.getItem('proposals_last_sync') || 'Never'
    }
  }
}

// Export singleton instance
export const proposalStorage = new ProposalStorageService()

// Export class for testing
export { ProposalStorageService }