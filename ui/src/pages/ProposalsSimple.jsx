import React from 'react'
import { Users, FileText } from 'lucide-react'

export default function ProposalsSimple() {
  console.log('Proposals page is rendering')
  
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

      {/* Test Content */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="card">
          <div className="flex items-center space-x-3 mb-4">
            <Users className="w-8 h-8 text-blue-600" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Active Proposals</h3>
              <p className="text-sm text-gray-500">2 proposals in progress</p>
            </div>
          </div>
          <p className="text-gray-600">
            View and manage your active contract proposals. Track progress, assign team members, and monitor deadlines.
          </p>
        </div>

        <div className="card">
          <div className="flex items-center space-x-3 mb-4">
            <FileText className="w-8 h-8 text-green-600" />
            <div>
              <h3 className="text-lg font-semibold text-gray-900">Available Opportunities</h3>
              <p className="text-sm text-gray-500">3 high-match opportunities</p>
            </div>
          </div>
          <p className="text-gray-600">
            Browse AI-matched opportunities from SAM.gov. Start new proposals directly from high-scoring matches.
          </p>
        </div>
      </div>

      {/* Sample Data */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Recent Opportunities</h3>
        <div className="space-y-3">
          <div className="p-3 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-900">IT Infrastructure Modernization Services</h4>
            <p className="text-sm text-gray-600">Department of Defense • 85% match • $2.5M</p>
          </div>
          <div className="p-3 bg-gray-50 rounded-lg">
            <h4 className="font-medium text-gray-900">Advanced Analytics Platform Development</h4>
            <p className="text-sm text-gray-600">Department of Navy • 78% match • $1.8M</p>
          </div>
        </div>
      </div>
    </div>
  )
}