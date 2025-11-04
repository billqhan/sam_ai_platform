import { useState } from 'react'

export default function ProposalsDebug() {
  const [activeTab, setActiveTab] = useState('proposals')

  console.log('ProposalsDebug rendering...')

  return (
    <div className="p-6 space-y-6">
      <h1 className="text-2xl font-bold">Proposals Debug</h1>
      <p>Active Tab: {activeTab}</p>
      <button 
        onClick={() => setActiveTab('test')}
        className="bg-blue-500 text-white px-4 py-2 rounded"
      >
        Test Button
      </button>
    </div>
  )
}