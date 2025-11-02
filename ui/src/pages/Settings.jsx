import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { settingsApi } from '../services/api'
import {
  Save,
  Building2,
  Mail,
  Bell,
  Shield,
  Database,
  Sliders
} from 'lucide-react'

export default function Settings() {
  const queryClient = useQueryClient()
  const [activeTab, setActiveTab] = useState('company')

  const { data: settings, isLoading } = useQuery({
    queryKey: ['settings'],
    queryFn: () => settingsApi.getAll(),
    select: (response) => response.data,
  })

  const saveMutation = useMutation({
    mutationFn: (data) => settingsApi.update(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['settings'] })
      alert('Settings saved successfully!')
    },
  })

  const handleSave = (formData) => {
    saveMutation.mutate(formData)
  }

  const tabs = [
    { id: 'company', name: 'Company Profile', icon: Building2 },
    { id: 'matching', name: 'Matching Settings', icon: Sliders },
    { id: 'notifications', name: 'Notifications', icon: Bell },
    { id: 'integrations', name: 'Integrations', icon: Database },
    { id: 'security', name: 'Security', icon: Shield },
  ]

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Settings</h1>
        <p className="mt-1 text-sm text-gray-500">
          Configure your RFP response agent preferences
        </p>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <nav className="space-y-1">
            {tabs.map((tab) => {
              const Icon = tab.icon
              return (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`w-full flex items-center px-4 py-3 text-sm font-medium rounded-lg transition-colors ${
                    activeTab === tab.id
                      ? 'bg-primary-50 text-primary-600'
                      : 'text-gray-700 hover:bg-gray-100'
                  }`}
                >
                  <Icon className="w-5 h-5 mr-3" />
                  {tab.name}
                </button>
              )
            })}
          </nav>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
          {activeTab === 'company' && <CompanySettings onSave={handleSave} />}
          {activeTab === 'matching' && <MatchingSettings onSave={handleSave} />}
          {activeTab === 'notifications' && <NotificationSettings onSave={handleSave} />}
          {activeTab === 'integrations' && <IntegrationSettings onSave={handleSave} />}
          {activeTab === 'security' && <SecuritySettings onSave={handleSave} />}
        </div>
      </div>
    </div>
  )
}

function CompanySettings({ onSave }) {
  const [formData, setFormData] = useState({
    companyName: 'L3Harris Technologies',
    contactEmail: 'contact@l3harris.com',
    description: 'L3Harris Technologies is a global aerospace and defense technology innovator, delivering solutions that connect and protect.',
    capabilities: 'Radar Systems, Electronic Warfare, Communication Systems, Space Technology',
    certifications: 'ISO 9001, CMMI Level 3, AS9100',
    pastPerformance: 'Multiple successful DoD contracts, NASA partnerships, Air Force radar systems',
  })

  return (
    <div className="space-y-6">
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Company Information</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Company Name
            </label>
            <input
              type="text"
              value={formData.companyName}
              onChange={(e) => setFormData({ ...formData, companyName: e.target.value })}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Contact Email
            </label>
            <input
              type="email"
              value={formData.contactEmail}
              onChange={(e) => setFormData({ ...formData, contactEmail: e.target.value })}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Company Description
            </label>
            <textarea
              rows={4}
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              className="input"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Core Capabilities
            </label>
            <textarea
              rows={3}
              value={formData.capabilities}
              onChange={(e) => setFormData({ ...formData, capabilities: e.target.value })}
              className="input"
              placeholder="List your company's core capabilities..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Certifications
            </label>
            <textarea
              rows={2}
              value={formData.certifications}
              onChange={(e) => setFormData({ ...formData, certifications: e.target.value })}
              className="input"
              placeholder="ISO, CMMI, etc..."
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Past Performance Highlights
            </label>
            <textarea
              rows={3}
              value={formData.pastPerformance}
              onChange={(e) => setFormData({ ...formData, pastPerformance: e.target.value })}
              className="input"
              placeholder="Notable projects and achievements..."
            />
          </div>
        </div>
      </div>
      <div className="flex justify-end">
        <button onClick={() => onSave(formData)} className="btn btn-primary">
          <Save className="w-4 h-4 mr-2" />
          Save Company Profile
        </button>
      </div>
    </div>
  )
}

function MatchingSettings({ onSave }) {
  const [formData, setFormData] = useState({
    matchThreshold: 0.7,
    maxResults: 100,
    enableKnowledgeBase: false,
    knowledgeBaseId: '',
    weightTitle: 0.3,
    weightDescription: 0.4,
    weightRequirements: 0.3,
  })

  return (
    <div className="space-y-6">
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Matching Algorithm</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Match Threshold (0.0 - 1.0)
            </label>
            <input
              type="number"
              min="0"
              max="1"
              step="0.1"
              value={formData.matchThreshold}
              onChange={(e) => setFormData({ ...formData, matchThreshold: parseFloat(e.target.value) })}
              className="input"
            />
            <p className="mt-1 text-xs text-gray-500">
              Minimum score to consider a match (current: {(formData.matchThreshold * 100).toFixed(0)}%)
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Opportunities to Process
            </label>
            <input
              type="number"
              min="1"
              value={formData.maxResults}
              onChange={(e) => setFormData({ ...formData, maxResults: parseInt(e.target.value) })}
              className="input"
            />
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="enableKB"
              checked={formData.enableKnowledgeBase}
              onChange={(e) => setFormData({ ...formData, enableKnowledgeBase: e.target.checked })}
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <label htmlFor="enableKB" className="ml-2 text-sm text-gray-700">
              Enable AWS Knowledge Base for Enhanced Matching
            </label>
          </div>
          {formData.enableKnowledgeBase && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Knowledge Base ID
              </label>
              <input
                type="text"
                value={formData.knowledgeBaseId}
                onChange={(e) => setFormData({ ...formData, knowledgeBaseId: e.target.value })}
                className="input"
                placeholder="Enter AWS Knowledge Base ID..."
              />
            </div>
          )}
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Matching Weights</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Title Weight: {(formData.weightTitle * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={formData.weightTitle}
              onChange={(e) => setFormData({ ...formData, weightTitle: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Description Weight: {(formData.weightDescription * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={formData.weightDescription}
              onChange={(e) => setFormData({ ...formData, weightDescription: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Requirements Weight: {(formData.weightRequirements * 100).toFixed(0)}%
            </label>
            <input
              type="range"
              min="0"
              max="1"
              step="0.1"
              value={formData.weightRequirements}
              onChange={(e) => setFormData({ ...formData, weightRequirements: parseFloat(e.target.value) })}
              className="w-full"
            />
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={() => onSave(formData)} className="btn btn-primary">
          <Save className="w-4 h-4 mr-2" />
          Save Matching Settings
        </button>
      </div>
    </div>
  )
}

function NotificationSettings({ onSave }) {
  const [formData, setFormData] = useState({
    emailEnabled: true,
    emailRecipients: 'admin@l3harris.com, bd@l3harris.com',
    dailyDigest: true,
    highQualityMatches: true,
    workflowErrors: true,
    digestTime: '08:00',
  })

  return (
    <div className="space-y-6">
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Email Notifications</h3>
        <div className="space-y-4">
          <div className="flex items-center">
            <input
              type="checkbox"
              id="emailEnabled"
              checked={formData.emailEnabled}
              onChange={(e) => setFormData({ ...formData, emailEnabled: e.target.checked })}
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <label htmlFor="emailEnabled" className="ml-2 text-sm text-gray-700">
              Enable Email Notifications
            </label>
          </div>
          {formData.emailEnabled && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Recipients (comma-separated)
                </label>
                <input
                  type="text"
                  value={formData.emailRecipients}
                  onChange={(e) => setFormData({ ...formData, emailRecipients: e.target.value })}
                  className="input"
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="dailyDigest"
                    checked={formData.dailyDigest}
                    onChange={(e) => setFormData({ ...formData, dailyDigest: e.target.checked })}
                    className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <label htmlFor="dailyDigest" className="ml-2 text-sm text-gray-700">
                    Daily Digest Reports
                  </label>
                </div>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="highQualityMatches"
                    checked={formData.highQualityMatches}
                    onChange={(e) => setFormData({ ...formData, highQualityMatches: e.target.checked })}
                    className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <label htmlFor="highQualityMatches" className="ml-2 text-sm text-gray-700">
                    Instant Alerts for High-Quality Matches (≥85%)
                  </label>
                </div>
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="workflowErrors"
                    checked={formData.workflowErrors}
                    onChange={(e) => setFormData({ ...formData, workflowErrors: e.target.checked })}
                    className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                  />
                  <label htmlFor="workflowErrors" className="ml-2 text-sm text-gray-700">
                    Workflow Errors and Failures
                  </label>
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Daily Digest Time
                </label>
                <input
                  type="time"
                  value={formData.digestTime}
                  onChange={(e) => setFormData({ ...formData, digestTime: e.target.value })}
                  className="input w-auto"
                />
              </div>
            </>
          )}
        </div>
      </div>
      <div className="flex justify-end">
        <button onClick={() => onSave(formData)} className="btn btn-primary">
          <Save className="w-4 h-4 mr-2" />
          Save Notification Settings
        </button>
      </div>
    </div>
  )
}

function IntegrationSettings({ onSave }) {
  return (
    <div className="space-y-6">
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">SAM.gov Integration</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              API Key
            </label>
            <input
              type="password"
              defaultValue="••••••••••••••••"
              className="input"
            />
            <p className="mt-1 text-xs text-gray-500">
              API key for downloading opportunities from SAM.gov
            </p>
          </div>
          <div className="flex items-center justify-between p-3 bg-success-50 rounded-lg">
            <span className="text-sm font-medium text-success-700">Status: Connected</span>
            <button className="btn btn-secondary btn-sm">Test Connection</button>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">AWS Services</h3>
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">Amazon Bedrock</p>
              <p className="text-xs text-gray-500">AI/ML matching service</p>
            </div>
            <span className="badge badge-success">Active</span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">Amazon S3</p>
              <p className="text-xs text-gray-500">Document storage</p>
            </div>
            <span className="badge badge-success">Active</span>
          </div>
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-900">Amazon SES</p>
              <p className="text-xs text-gray-500">Email notifications</p>
            </div>
            <span className="badge badge-success">Active</span>
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={() => onSave({})} className="btn btn-primary">
          <Save className="w-4 h-4 mr-2" />
          Save Integration Settings
        </button>
      </div>
    </div>
  )
}

function SecuritySettings({ onSave }) {
  return (
    <div className="space-y-6">
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Access Control</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Authentication Method
            </label>
            <select className="input">
              <option>Amazon Cognito</option>
              <option>Active Directory</option>
              <option>SAML 2.0</option>
            </select>
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="mfa"
              defaultChecked
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <label htmlFor="mfa" className="ml-2 text-sm text-gray-700">
              Require Multi-Factor Authentication (MFA)
            </label>
          </div>
        </div>
      </div>

      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Data Protection</h3>
        <div className="space-y-4">
          <div className="flex items-center">
            <input
              type="checkbox"
              id="encryption"
              defaultChecked
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <label htmlFor="encryption" className="ml-2 text-sm text-gray-700">
              Encrypt data at rest (S3, DynamoDB)
            </label>
          </div>
          <div className="flex items-center">
            <input
              type="checkbox"
              id="audit"
              defaultChecked
              className="w-4 h-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
            />
            <label htmlFor="audit" className="ml-2 text-sm text-gray-700">
              Enable CloudTrail audit logging
            </label>
          </div>
        </div>
      </div>

      <div className="flex justify-end">
        <button onClick={() => onSave({})} className="btn btn-primary">
          <Save className="w-4 h-4 mr-2" />
          Save Security Settings
        </button>
      </div>
    </div>
  )
}
