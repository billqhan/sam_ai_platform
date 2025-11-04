import React from 'react'

export default function TestPage() {
  return (
    <div className="p-6">
      <h1 className="text-2xl font-bold text-gray-900 mb-4">Test Page</h1>
      <p className="text-gray-600">If you can see this, the React app is working correctly.</p>
      <div className="mt-4 p-4 bg-blue-50 border border-blue-200 rounded-lg">
        <p className="text-blue-800">
          Current time: {new Date().toLocaleString()}
        </p>
      </div>
    </div>
  )
}