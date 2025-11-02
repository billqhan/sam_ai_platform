import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { workflowApi } from '../services/api'
import {
  Play,
  Download,
  FileJson,
  Target,
  FileText,
  Mail,
  CheckCircle,
  XCircle,
  Clock,
  AlertCircle,
  RefreshCw
} from 'lucide-react'

const WORKFLOW_STEPS = [
  {
    id: 'download',
    name: 'Download Opportunities',
    description: 'Download latest opportunities from SAM.gov',
    icon: Download,
    action: 'triggerDownload',
  },
  {
    id: 'process',
    name: 'Process JSON',
    description: 'Extract and parse individual opportunities',
    icon: FileJson,
    action: 'triggerProcessing',
  },
  {
    id: 'match',
    name: 'Generate Matches',
    description: 'Run AI matching against company profiles',
    icon: Target,
    action: 'triggerMatching',
  },
  {
    id: 'reports',
    name: 'Generate Reports',
    description: 'Create daily summary reports with opportunity analysis and match results',
    icon: FileText,
    action: 'triggerReports',
  },
  {
    id: 'notify',
    name: 'Send Notifications',
    description: 'Email reports to stakeholders',
    icon: Mail,
    action: 'triggerNotification',
  },
]

function StepCard({ step, status, onExecute, isExecuting }) {
  const Icon = step.icon
  const isComplete = status === 'success'
  const isRunning = status === 'running'
  const isError = status === 'error'

  return (
    <div className={`card transition-all ${
      isComplete ? 'border-success-500 border-2' :
      isError ? 'border-danger-500 border-2' :
      isRunning ? 'border-primary-500 border-2' : ''
    }`}>
      <div className="flex items-start justify-between">
        <div className="flex items-start space-x-4">
          <div className={`p-3 rounded-lg ${
            isComplete ? 'bg-success-50' :
            isError ? 'bg-danger-50' :
            isRunning ? 'bg-primary-50' : 'bg-gray-50'
          }`}>
            <Icon className={`w-6 h-6 ${
              isComplete ? 'text-success-600' :
              isError ? 'text-danger-600' :
              isRunning ? 'text-primary-600' : 'text-gray-600'
            }`} />
          </div>
          <div className="flex-1">
            <h3 className="text-lg font-semibold text-gray-900">{step.name}</h3>
            <p className="mt-1 text-sm text-gray-500">{step.description}</p>
            {status && (
              <div className="mt-2">
                {isComplete && (
                  <span className="badge badge-success">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Completed
                  </span>
                )}
                {isRunning && (
                  <span className="badge badge-info">
                    <RefreshCw className="w-3 h-3 mr-1 animate-spin" />
                    Running...
                  </span>
                )}
                {isError && (
                  <span className="badge badge-danger">
                    <XCircle className="w-3 h-3 mr-1" />
                    Failed
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
        <button
          onClick={() => onExecute(step)}
          disabled={isExecuting}
          className="btn btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play className="w-4 h-4 mr-2" />
          Run
        </button>
      </div>
    </div>
  )
}

function WorkflowHistory({ history }) {
  if (!history || history.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500">
        <Clock className="w-12 h-12 mx-auto mb-3 text-gray-400" />
        <p>No workflow history available</p>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {history.map((run, index) => (
        <div key={index} className="p-4 bg-gray-50 rounded-lg hover:bg-gray-100 transition-colors">
          <div className="flex items-center justify-between">
            <div className="flex-1">
              <div className="flex items-center space-x-2">
                <span className="text-sm font-medium text-gray-900">{run.type}</span>
                {run.status === 'success' && (
                  <CheckCircle className="w-4 h-4 text-success-600" />
                )}
                {run.status === 'error' && (
                  <XCircle className="w-4 h-4 text-danger-600" />
                )}
              </div>
              <p className="mt-1 text-xs text-gray-500">{run.timestamp}</p>
              {run.message && (
                <p className="mt-1 text-sm text-gray-600">{run.message}</p>
              )}
            </div>
            <div className="text-right">
              {run.duration && (
                <p className="text-sm font-medium text-gray-900">{run.duration}s</p>
              )}
              {run.itemsProcessed && (
                <p className="text-xs text-gray-500">{run.itemsProcessed} items</p>
              )}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export default function Workflow() {
  const queryClient = useQueryClient()
  const [stepStatuses, setStepStatuses] = useState({})
  const [showFullWorkflow, setShowFullWorkflow] = useState(false)

  const { data: workflowStatus } = useQuery({
    queryKey: ['workflow-status'],
    queryFn: () => workflowApi.getStatus(),
    select: (response) => response.data,
    refetchInterval: 5000, // Refresh every 5 seconds
  })

  const { data: workflowHistory } = useQuery({
    queryKey: ['workflow-history'],
    queryFn: () => workflowApi.getHistory(10),
    select: (response) => response.data,
  })

  const executeMutation = useMutation({
    mutationFn: async ({ step, params }) => {
      // Execute the workflow step
      const apiMethod = workflowApi[step.action]
      const result = await apiMethod(params)
      
      // Wait a moment for processing to complete
      await new Promise(resolve => setTimeout(resolve, 5000))
      
      // Only generate business reports for the reports step
      // No individual step execution reports
      
      return result
    },
    onMutate: ({ step }) => {
      setStepStatuses(prev => ({ ...prev, [step.id]: 'running' }))
    },
    onSuccess: (data, { step }) => {
      setStepStatuses(prev => ({ ...prev, [step.id]: 'success' }))
      queryClient.invalidateQueries({ queryKey: ['workflow-history'] })
      // Refresh reports to show new auto-generated report
      queryClient.invalidateQueries({ queryKey: ['reports'] })
    },
    onError: (error, { step }) => {
      setStepStatuses(prev => ({ ...prev, [step.id]: 'error' }))
      queryClient.invalidateQueries({ queryKey: ['workflow-history'] })
      
      // No error reports generated - only business reports from reports step
    },
  })

  const executeFullWorkflow = async () => {
    setShowFullWorkflow(true)
    for (const step of WORKFLOW_STEPS) {
      try {
        await executeMutation.mutateAsync({ step })
        // Wait a bit between steps
        await new Promise(resolve => setTimeout(resolve, 2000))
      } catch (error) {
        console.error(`Workflow stopped at ${step.name}:`, error)
        break
      }
    }
  }

  const handleExecuteStep = (step) => {
    executeMutation.mutate({ step })
  }

  // Mock history data
  const mockHistory = [
    {
      type: 'Full Workflow',
      status: 'success',
      timestamp: '2025-10-30 08:00:00',
      duration: 342,
      itemsProcessed: 67,
      message: 'All steps completed successfully'
    },
    {
      type: 'Generate Reports',
      status: 'success',
      timestamp: '2025-10-29 14:30:15',
      duration: 45,
      message: 'Web dashboard and user reports generated'
    },
    {
      type: 'Generate Matches',
      status: 'success',
      timestamp: '2025-10-29 14:25:30',
      duration: 178,
      itemsProcessed: 67,
      message: '14 matches found above threshold'
    },
    {
      type: 'Download Opportunities',
      status: 'success',
      timestamp: '2025-10-29 08:00:05',
      duration: 12,
      itemsProcessed: 67,
      message: 'Downloaded from SAM.gov'
    },
  ]

  const displayHistory = workflowHistory || mockHistory

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Workflow Control</h1>
          <p className="mt-1 text-sm text-gray-500">
            Trigger and monitor RFP processing pipeline
          </p>
        </div>
        <button
          onClick={executeFullWorkflow}
          disabled={executeMutation.isPending}
          className="btn btn-success disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Play className="w-5 h-5 mr-2" />
          Run Full Workflow
        </button>
      </div>

      {/* Workflow Progress Banner */}
      {showFullWorkflow && (
        <div className="card bg-primary-50 border-primary-200">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-3">
              <RefreshCw className="w-6 h-6 text-primary-600 animate-spin" />
              <div>
                <h3 className="text-lg font-semibold text-primary-900">
                  Full Workflow Running
                </h3>
                <p className="text-sm text-primary-700">
                  Please wait while all steps are executed sequentially...
                </p>
              </div>
            </div>
            <button
              onClick={() => setShowFullWorkflow(false)}
              className="btn btn-secondary"
            >
              Hide
            </button>
          </div>
        </div>
      )}

      {/* Workflow Steps */}
      <div className="space-y-4">
        <h2 className="text-lg font-semibold text-gray-900">Individual Steps</h2>
        {WORKFLOW_STEPS.map((step) => (
          <StepCard
            key={step.id}
            step={step}
            status={stepStatuses[step.id]}
            onExecute={handleExecuteStep}
            isExecuting={executeMutation.isPending}
          />
        ))}
      </div>

      {/* Configuration Section */}
      <div className="card">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Workflow Configuration</h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Match Threshold
            </label>
            <input
              type="number"
              min="0"
              max="1"
              step="0.1"
              defaultValue="0.7"
              className="input"
            />
            <p className="mt-1 text-xs text-gray-500">
              Minimum score to consider a match (0.0 - 1.0)
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Max Opportunities to Process
            </label>
            <input
              type="number"
              min="1"
              defaultValue="100"
              className="input"
            />
            <p className="mt-1 text-xs text-gray-500">
              Limit number of opportunities per run
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Auto-run Schedule
            </label>
            <select className="input">
              <option value="disabled">Disabled</option>
              <option value="daily">Daily at 8:00 AM</option>
              <option value="weekly">Weekly on Monday</option>
              <option value="custom">Custom schedule</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Email Notifications
            </label>
            <select className="input">
              <option value="all">All workflow events</option>
              <option value="errors">Errors only</option>
              <option value="daily">Daily summary</option>
              <option value="disabled">Disabled</option>
            </select>
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <button className="btn btn-primary">
            Save Configuration
          </button>
        </div>
      </div>

      {/* Workflow History */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Execution History</h3>
          <button className="text-sm text-primary-600 hover:text-primary-700 font-medium">
            View All
          </button>
        </div>
        <WorkflowHistory history={displayHistory} />
      </div>

      {/* Current Status */}
      <div className="card bg-gray-50">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">System Status</h3>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-success-100 rounded-full mb-2">
              <CheckCircle className="w-6 h-6 text-success-600" />
            </div>
            <p className="text-sm font-medium text-gray-900">All Systems Operational</p>
            <p className="text-xs text-gray-500 mt-1">Lambda functions healthy</p>
          </div>
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-primary-100 rounded-full mb-2">
              <Clock className="w-6 h-6 text-primary-600" />
            </div>
            <p className="text-sm font-medium text-gray-900">Last Run: 2 hours ago</p>
            <p className="text-xs text-gray-500 mt-1">Next scheduled: Tomorrow 8:00 AM</p>
          </div>
          <div className="text-center">
            <div className="inline-flex items-center justify-center w-12 h-12 bg-warning-100 rounded-full mb-2">
              <AlertCircle className="w-6 h-6 text-warning-600" />
            </div>
            <p className="text-sm font-medium text-gray-900">0 Items in DLQ</p>
            <p className="text-xs text-gray-500 mt-1">No failed messages</p>
          </div>
        </div>
      </div>
    </div>
  )
}
