import { useState, useEffect } from 'react'
import { 
  Plus, 
  Trash2, 
  Save, 
  FileText, 
  Download, 
  Upload,
  Edit3,
  Check,
  X
} from 'lucide-react'

export default function Compliance() {
  const [tables, setTables] = useState([])
  const [activeTableId, setActiveTableId] = useState(null)
  const [editingCell, setEditingCell] = useState(null)
  const [isCreatingTable, setIsCreatingTable] = useState(false)
  const [newTableName, setNewTableName] = useState('')

  // Initialize with sample data
  useEffect(() => {
    const sampleTables = [
      {
        id: 'table-1',
        name: 'Security Requirements Matrix',
        description: 'Security compliance requirements and implementation status',
        lastModified: new Date().toISOString(),
        data: [
          ['Requirement ID', 'Requirement Description', 'Implementation Status', 'Comments', 'Evidence'],
          ['SEC-001', 'Data encryption at rest', 'Compliant', 'AES-256 encryption implemented', 'Security assessment doc'],
          ['SEC-002', 'Multi-factor authentication', 'Partially Compliant', 'MFA for admin users only', 'Configuration screenshots'],
          ['SEC-003', 'Regular security audits', 'Non-Compliant', 'Quarterly audits not established', 'N/A'],
          ['SEC-004', 'Access control policies', 'Compliant', 'Role-based access implemented', 'Policy document']
        ]
      },
      {
        id: 'table-2',
        name: 'Technical Specifications',
        description: 'Technical requirements and compliance status',
        lastModified: new Date().toISOString(),
        data: [
          ['Specification', 'Required Value', 'Current Value', 'Status', 'Notes'],
          ['CPU Performance', '≥ 2.5 GHz', '3.2 GHz', 'Meets', 'Intel Xeon processor'],
          ['Memory', '≥ 16 GB RAM', '32 GB RAM', 'Exceeds', 'DDR4 memory'],
          ['Storage', '≥ 1 TB SSD', '2 TB NVMe', 'Exceeds', 'High-performance storage'],
          ['Network', '≥ 1 Gbps', '10 Gbps', 'Exceeds', 'Fiber connection']
        ]
      }
    ]
    setTables(sampleTables)
    setActiveTableId(sampleTables[0]?.id)
  }, [])

  const activeTable = tables.find(table => table.id === activeTableId)

  const createNewTable = () => {
    if (!newTableName.trim()) return
    
    const newTable = {
      id: `table-${Date.now()}`,
      name: newTableName,
      description: 'New compliance table',
      lastModified: new Date().toISOString(),
      data: [
        ['Column 1', 'Column 2', 'Column 3'],
        ['', '', ''],
        ['', '', '']
      ]
    }
    
    setTables([...tables, newTable])
    setActiveTableId(newTable.id)
    setNewTableName('')
    setIsCreatingTable(false)
  }

  const deleteTable = (tableId) => {
    if (window.confirm('Are you sure you want to delete this table?')) {
      setTables(tables.filter(table => table.id !== tableId))
      if (activeTableId === tableId) {
        setActiveTableId(tables.find(table => table.id !== tableId)?.id || null)
      }
    }
  }

  const updateCell = (rowIndex, colIndex, value) => {
    const updatedTables = tables.map(table => {
      if (table.id === activeTableId) {
        const newData = [...table.data]
        newData[rowIndex][colIndex] = value
        return {
          ...table,
          data: newData,
          lastModified: new Date().toISOString()
        }
      }
      return table
    })
    setTables(updatedTables)
  }

  const addRow = () => {
    if (!activeTable) return
    
    const updatedTables = tables.map(table => {
      if (table.id === activeTableId) {
        const newRow = new Array(table.data[0].length).fill('')
        return {
          ...table,
          data: [...table.data, newRow],
          lastModified: new Date().toISOString()
        }
      }
      return table
    })
    setTables(updatedTables)
  }

  const addColumn = () => {
    if (!activeTable) return
    
    const updatedTables = tables.map(table => {
      if (table.id === activeTableId) {
        const newData = table.data.map(row => [...row, ''])
        return {
          ...table,
          data: newData,
          lastModified: new Date().toISOString()
        }
      }
      return table
    })
    setTables(updatedTables)
  }

  const deleteRow = (rowIndex) => {
    if (!activeTable || rowIndex === 0) return // Don't delete header row
    
    const updatedTables = tables.map(table => {
      if (table.id === activeTableId) {
        const newData = table.data.filter((_, index) => index !== rowIndex)
        return {
          ...table,
          data: newData,
          lastModified: new Date().toISOString()
        }
      }
      return table
    })
    setTables(updatedTables)
  }

  const exportTable = () => {
    if (!activeTable) return
    
    const csvContent = activeTable.data
      .map(row => row.map(cell => `"${cell}"`).join(','))
      .join('\\n')
    
    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = `${activeTable.name}.csv`
    link.click()
    window.URL.revokeObjectURL(url)
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Compliance Management</h1>
        <p className="text-gray-600 mt-2">
          Create and manage compliance tables for requirements tracking and documentation.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Table List Sidebar */}
        <div className="lg:col-span-1">
          <div className="bg-white rounded-lg shadow p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold">Compliance Tables</h2>
              <button
                onClick={() => setIsCreatingTable(true)}
                className="btn btn-primary btn-sm"
              >
                <Plus className="w-4 h-4 mr-1" />
                New
              </button>
            </div>

            {isCreatingTable && (
              <div className="mb-4 p-3 border rounded-lg bg-gray-50">
                <input
                  type="text"
                  placeholder="Table name"
                  value={newTableName}
                  onChange={(e) => setNewTableName(e.target.value)}
                  className="input input-sm w-full mb-2"
                  autoFocus
                />
                <div className="flex space-x-2">
                  <button
                    onClick={createNewTable}
                    className="btn btn-primary btn-sm"
                  >
                    <Check className="w-4 h-4" />
                  </button>
                  <button
                    onClick={() => {
                      setIsCreatingTable(false)
                      setNewTableName('')
                    }}
                    className="btn btn-secondary btn-sm"
                  >
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-2">
              {tables.map(table => (
                <div
                  key={table.id}
                  className={`p-3 rounded-lg border cursor-pointer transition-colors ${
                    activeTableId === table.id
                      ? 'border-primary-300 bg-primary-50'
                      : 'border-gray-200 hover:border-gray-300'
                  }`}
                  onClick={() => setActiveTableId(table.id)}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-sm font-medium text-gray-900 truncate">
                        {table.name}
                      </h3>
                      <p className="text-xs text-gray-500 mt-1 truncate">
                        {table.description}
                      </p>
                      <p className="text-xs text-gray-400 mt-1">
                        Modified: {new Date(table.lastModified).toLocaleDateString()}
                      </p>
                    </div>
                    <button
                      onClick={(e) => {
                        e.stopPropagation()
                        deleteTable(table.id)
                      }}
                      className="text-red-400 hover:text-red-600 ml-2"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Table Editor */}
        <div className="lg:col-span-3">
          {activeTable ? (
            <div className="bg-white rounded-lg shadow">
              {/* Table Header */}
              <div className="p-4 border-b border-gray-200">
                <div className="flex items-center justify-between">
                  <div>
                    <h2 className="text-lg font-semibold text-gray-900">
                      {activeTable.name}
                    </h2>
                    <p className="text-sm text-gray-600 mt-1">
                      {activeTable.description}
                    </p>
                  </div>
                  <div className="flex space-x-2">
                    <button
                      onClick={addColumn}
                      className="btn btn-secondary btn-sm"
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Column
                    </button>
                    <button
                      onClick={addRow}
                      className="btn btn-secondary btn-sm"
                    >
                      <Plus className="w-4 h-4 mr-1" />
                      Row
                    </button>
                    <button
                      onClick={exportTable}
                      className="btn btn-primary btn-sm"
                    >
                      <Download className="w-4 h-4 mr-1" />
                      Export
                    </button>
                  </div>
                </div>
              </div>

              {/* Table Content */}
              <div className="p-4">
                <div className="overflow-x-auto">
                  <table className="w-full border-collapse border border-gray-300">
                    <tbody>
                      {activeTable.data.map((row, rowIndex) => (
                        <tr key={rowIndex}>
                          {row.map((cell, colIndex) => (
                            <td
                              key={colIndex}
                              className={`border border-gray-300 p-2 relative group ${
                                rowIndex === 0 ? 'bg-gray-50 font-medium' : 'bg-white'
                              }`}
                            >
                              {editingCell?.row === rowIndex && editingCell?.col === colIndex ? (
                                <input
                                  type="text"
                                  value={cell}
                                  onChange={(e) => updateCell(rowIndex, colIndex, e.target.value)}
                                  onBlur={() => setEditingCell(null)}
                                  onKeyDown={(e) => {
                                    if (e.key === 'Enter') {
                                      setEditingCell(null)
                                    }
                                    if (e.key === 'Escape') {
                                      setEditingCell(null)
                                    }
                                  }}
                                  className="w-full border-none outline-none bg-transparent"
                                  autoFocus
                                />
                              ) : (
                                <div
                                  onClick={() => setEditingCell({ row: rowIndex, col: colIndex })}
                                  className="min-h-[20px] cursor-text"
                                >
                                  {cell || <span className="text-gray-400">Click to edit</span>}
                                </div>
                              )}
                              
                              {rowIndex > 0 && colIndex === 0 && (
                                <button
                                  onClick={() => deleteRow(rowIndex)}
                                  className="absolute -left-6 top-1/2 transform -translate-y-1/2 opacity-0 group-hover:opacity-100 text-red-400 hover:text-red-600 transition-opacity"
                                >
                                  <Trash2 className="w-4 h-4" />
                                </button>
                              )}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white rounded-lg shadow p-8 text-center">
              <FileText className="w-12 h-12 text-gray-400 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">No Table Selected</h3>
              <p className="text-gray-600">
                Select a table from the sidebar or create a new one to get started.
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}