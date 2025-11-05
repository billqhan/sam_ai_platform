import { useState, useEffect } from 'react'
import {
  MessageSquare,
  Save,
  RefreshCw,
  FileText,
  Star,
  TrendingUp,
  Edit3,
  Copy,
  Download,
  Upload,
  Plus,
  Trash2
} from 'lucide-react'

export default function Prompts() {
  const [activeTab, setActiveTab] = useState('matching')
  const [prompts, setPrompts] = useState({
    matchingPrompt: '',
    scoringPrompt: '',
    categoryPrompt: ''
  })
  const [customPrompts, setCustomPrompts] = useState([])
  const [isSaving, setIsSaving] = useState(false)
  const [lastSaved, setLastSaved] = useState(null)

  // Load prompts from localStorage on component mount
  useEffect(() => {
    const savedPrompts = localStorage.getItem('ai-matching-prompts')
    const savedCustomPrompts = localStorage.getItem('custom-prompts')
    
    if (savedPrompts) {
      setPrompts(JSON.parse(savedPrompts))
    } else {
      // Default prompts
      setPrompts({
        matchingPrompt: `Analyze the following government opportunity and determine how well it matches our company's capabilities. Consider:

1. Technical requirements alignment
2. Past experience relevance  
3. Team expertise match
4. Contract size and scope fit
5. Timeline feasibility

Provide a detailed analysis of strengths, potential challenges, and overall match quality.`,
        
        scoringPrompt: `Rate this opportunity match on a scale of 0.0 to 1.0 based on:

- Technical capability alignment (30%)
- Past performance relevance (25%) 
- Team availability and expertise (20%)
- Contract value and profitability (15%)
- Timeline and resource feasibility (10%)

Provide the numerical score and brief justification.`,
        
        categoryPrompt: `Categorize this opportunity into one of the following categories:

1. High Priority - Excellent fit, pursue aggressively
2. Medium Priority - Good fit with some gaps to address
3. Low Priority - Marginal fit, consider if resources allow
4. No Bid - Poor fit or significant barriers

Explain the category selection reasoning.`
      })
    }

    if (savedCustomPrompts) {
      setCustomPrompts(JSON.parse(savedCustomPrompts))
    }

    // Load last saved timestamp
    const lastSavedTime = localStorage.getItem('prompts-last-saved')
    if (lastSavedTime) {
      setLastSaved(new Date(lastSavedTime))
    }
  }, [])

  const handleSave = async () => {
    setIsSaving(true)
    
    // Simulate save delay
    await new Promise(resolve => setTimeout(resolve, 500))
    
    localStorage.setItem('ai-matching-prompts', JSON.stringify(prompts))
    localStorage.setItem('custom-prompts', JSON.stringify(customPrompts))
    const now = new Date()
    localStorage.setItem('prompts-last-saved', now.toISOString())
    
    setLastSaved(now)
    setIsSaving(false)
  }

  const resetToDefaults = () => {
    if (window.confirm('Are you sure you want to reset all prompts to defaults? This cannot be undone.')) {
      const defaultPrompts = {
        matchingPrompt: `Analyze the following government opportunity and determine how well it matches our company's capabilities. Consider:

1. Technical requirements alignment
2. Past experience relevance  
3. Team expertise match
4. Contract size and scope fit
5. Timeline feasibility

Provide a detailed analysis of strengths, potential challenges, and overall match quality.`,
        
        scoringPrompt: `Rate this opportunity match on a scale of 0.0 to 1.0 based on:

- Technical capability alignment (30%)
- Past performance relevance (25%) 
- Team availability and expertise (20%)
- Contract value and profitability (15%)
- Timeline and resource feasibility (10%)

Provide the numerical score and brief justification.`,
        
        categoryPrompt: `Categorize this opportunity into one of the following categories:

1. High Priority - Excellent fit, pursue aggressively
2. Medium Priority - Good fit with some gaps to address
3. Low Priority - Marginal fit, consider if resources allow
4. No Bid - Poor fit or significant barriers

Explain the category selection reasoning.`
      }
      setPrompts(defaultPrompts)
    }
  }

  const copyPrompt = (promptText) => {
    navigator.clipboard.writeText(promptText)
    // You could add a toast notification here
  }

  const exportPrompts = () => {
    const data = {
      aiMatchingPrompts: prompts,
      customPrompts: customPrompts,
      exportDate: new Date().toISOString()
    }
    
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'ai-prompts-backup.json'
    link.click()
    window.URL.revokeObjectURL(url)
  }

  const addCustomPrompt = () => {
    const newPrompt = {
      id: Date.now(),
      name: 'New Custom Prompt',
      description: 'Custom prompt description',
      content: 'Enter your custom prompt here...',
      category: 'General',
      createdDate: new Date().toISOString()
    }
    setCustomPrompts([...customPrompts, newPrompt])
  }

  const updateCustomPrompt = (id, field, value) => {
    setCustomPrompts(customPrompts.map(prompt => 
      prompt.id === id ? { ...prompt, [field]: value } : prompt
    ))
  }

  const deleteCustomPrompt = (id) => {
    if (window.confirm('Are you sure you want to delete this custom prompt?')) {
      setCustomPrompts(customPrompts.filter(prompt => prompt.id !== id))
    }
  }

  const tabs = [
    { id: 'matching', name: 'AI Matching', icon: TrendingUp },
    { id: 'custom', name: 'Custom Prompts', icon: Edit3 }
  ]

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">AI Prompt Management</h1>
        <p className="text-gray-600 mt-2">
          Configure and manage AI prompts used for opportunity matching, scoring, and analysis.
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="border-b border-gray-200 mb-6">
        <nav className="flex space-x-8">
          {tabs.map(tab => {
            const Icon = tab.icon
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`flex items-center py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                <Icon className="w-4 h-4 mr-2" />
                {tab.name}
              </button>
            )
          })}
        </nav>
      </div>

      {/* AI Matching Prompts Tab */}
      {activeTab === 'matching' && (
        <div className="space-y-6">
          {/* Header Actions */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">AI Matching Prompts</h2>
              <p className="text-sm text-gray-600 mt-1">
                Configure the prompts used for AI-powered opportunity analysis and scoring.
              </p>
            </div>
            <div className="flex items-center space-x-3">
              <button
                onClick={resetToDefaults}
                className="btn btn-secondary btn-sm"
              >
                <RefreshCw className="w-4 h-4 mr-1" />
                Reset to Defaults
              </button>
              <button
                onClick={exportPrompts}
                className="btn btn-secondary btn-sm"
              >
                <Download className="w-4 h-4 mr-1" />
                Export
              </button>
              <button
                onClick={handleSave}
                disabled={isSaving}
                className="btn btn-primary btn-sm"
              >
                {isSaving ? (
                  <RefreshCw className="w-4 h-4 mr-1 animate-spin" />
                ) : (
                  <Save className="w-4 h-4 mr-1" />
                )}
                Save Changes
              </button>
            </div>
          </div>

          {/* Last Saved Indicator */}
          {lastSaved && (
            <div className="text-sm text-gray-500">
              Last saved: {lastSaved.toLocaleString()}
            </div>
          )}

          {/* Prompt Editors */}
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {/* Matching Analysis Prompt */}
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center">
                  <Star className="w-5 h-5 text-primary-500 mr-2" />
                  <h3 className="text-md font-medium text-gray-900">
                    Matching Analysis
                  </h3>
                </div>
                <button
                  onClick={() => copyPrompt(prompts.matchingPrompt)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
              <p className="text-sm text-gray-600 mb-3">
                Guides AI in analyzing how well opportunities match company capabilities.
              </p>
              <textarea
                value={prompts.matchingPrompt}
                onChange={(e) => setPrompts({ ...prompts, matchingPrompt: e.target.value })}
                rows={12}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="Enter the matching analysis prompt..."
              />
            </div>

            {/* Scoring Prompt */}
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center">
                  <TrendingUp className="w-5 h-5 text-success-500 mr-2" />
                  <h3 className="text-md font-medium text-gray-900">
                    Scoring Criteria
                  </h3>
                </div>
                <button
                  onClick={() => copyPrompt(prompts.scoringPrompt)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
              <p className="text-sm text-gray-600 mb-3">
                Defines how AI assigns numerical scores to opportunity matches.
              </p>
              <textarea
                value={prompts.scoringPrompt}
                onChange={(e) => setPrompts({ ...prompts, scoringPrompt: e.target.value })}
                rows={12}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="Enter the scoring prompt..."
              />
            </div>

            {/* Category Prompt */}
            <div className="bg-white border border-gray-200 rounded-lg p-4">
              <div className="flex items-center justify-between mb-3">
                <div className="flex items-center">
                  <FileText className="w-5 h-5 text-warning-500 mr-2" />
                  <h3 className="text-md font-medium text-gray-900">
                    Categorization
                  </h3>
                </div>
                <button
                  onClick={() => copyPrompt(prompts.categoryPrompt)}
                  className="text-gray-400 hover:text-gray-600"
                >
                  <Copy className="w-4 h-4" />
                </button>
              </div>
              <p className="text-sm text-gray-600 mb-3">
                Guides AI in categorizing opportunities by priority level.
              </p>
              <textarea
                value={prompts.categoryPrompt}
                onChange={(e) => setPrompts({ ...prompts, categoryPrompt: e.target.value })}
                rows={12}
                className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                placeholder="Enter the categorization prompt..."
              />
            </div>
          </div>
        </div>
      )}

      {/* Custom Prompts Tab */}
      {activeTab === 'custom' && (
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h2 className="text-lg font-semibold text-gray-900">Custom Prompts</h2>
              <p className="text-sm text-gray-600 mt-1">
                Create and manage custom prompts for specialized analysis tasks.
              </p>
            </div>
            <button
              onClick={addCustomPrompt}
              className="btn btn-primary"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Custom Prompt
            </button>
          </div>

          {/* Custom Prompts List */}
          {customPrompts.length === 0 ? (
            <div className="text-center py-12">
              <MessageSquare className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Custom Prompts</h3>
              <p className="text-gray-600 mb-4">
                Create custom prompts for specialized analysis and matching scenarios.
              </p>
              <button
                onClick={addCustomPrompt}
                className="btn btn-primary"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Your First Custom Prompt
              </button>
            </div>
          ) : (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {customPrompts.map(prompt => (
                <div key={prompt.id} className="bg-white border border-gray-200 rounded-lg p-4">
                  <div className="flex items-start justify-between mb-3">
                    <div className="flex-1">
                      <input
                        type="text"
                        value={prompt.name}
                        onChange={(e) => updateCustomPrompt(prompt.id, 'name', e.target.value)}
                        className="text-md font-medium text-gray-900 border-none outline-none bg-transparent w-full"
                      />
                      <input
                        type="text"
                        value={prompt.description}
                        onChange={(e) => updateCustomPrompt(prompt.id, 'description', e.target.value)}
                        className="text-sm text-gray-600 border-none outline-none bg-transparent w-full mt-1"
                        placeholder="Prompt description..."
                      />
                    </div>
                    <div className="flex items-center space-x-1 ml-2">
                      <button
                        onClick={() => copyPrompt(prompt.content)}
                        className="text-gray-400 hover:text-gray-600"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteCustomPrompt(prompt.id)}
                        className="text-red-400 hover:text-red-600"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <textarea
                    value={prompt.content}
                    onChange={(e) => updateCustomPrompt(prompt.id, 'content', e.target.value)}
                    rows={8}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
                    placeholder="Enter your custom prompt..."
                  />
                  <div className="flex items-center justify-between mt-3">
                    <input
                      type="text"
                      value={prompt.category}
                      onChange={(e) => updateCustomPrompt(prompt.id, 'category', e.target.value)}
                      placeholder="Category"
                      className="text-xs text-gray-500 border border-gray-200 rounded px-2 py-1 w-24"
                    />
                    <span className="text-xs text-gray-400">
                      Created: {new Date(prompt.createdDate).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}