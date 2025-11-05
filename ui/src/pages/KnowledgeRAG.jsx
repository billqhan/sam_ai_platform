import { useState, useEffect, useRef } from 'react'
import { 
  Upload, 
  File, 
  FileText, 
  Image, 
  Archive,
  Download, 
  Trash2, 
  Search, 
  Eye,
  Database,
  RefreshCw
} from 'lucide-react'

export default function KnowledgeRAG() {
  const [documents, setDocuments] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedFolder, setSelectedFolder] = useState('All')
  const [viewMode, setViewMode] = useState('grid')
  const [isRetrieving, setIsRetrieving] = useState(false)
  const fileInputRef = useRef(null)

  // Sample documents data
  useEffect(() => {
    const sampleDocs = [
      {
        id: 'doc-1',
        name: 'Company Capabilities Overview.pdf',
        type: 'pdf',
        size: 2453760,
        folder: 'Proposals',
        uploadDate: '2025-11-01T10:30:00Z',
        uploadedBy: 'John Smith',
        description: 'Comprehensive overview of company technical capabilities'
      },
      {
        id: 'doc-2',
        name: 'Security Compliance Matrix.xlsx',
        type: 'excel',
        size: 1024000,
        folder: 'Compliance',
        uploadDate: '2025-10-28T14:15:00Z',
        uploadedBy: 'Sarah Johnson',
        description: 'Security requirements compliance tracking matrix'
      },
      {
        id: 'doc-3',
        name: 'Technical Architecture Diagram.png',
        type: 'image',
        size: 856432,
        folder: 'Technical Specs',
        uploadDate: '2025-10-25T09:45:00Z',
        uploadedBy: 'Mike Chen',
        description: 'System architecture diagram for cloud infrastructure'
      }
    ]
    setDocuments(sampleDocs)
  }, [])

  const getFileIcon = (type) => {
    switch (type) {
      case 'pdf': 
        return <FileText className="w-8 h-8 text-red-500" />
      case 'excel': 
        return <FileText className="w-8 h-8 text-green-500" />
      case 'image': 
        return <Image className="w-8 h-8 text-purple-500" />
      case 'archive': 
        return <Archive className="w-8 h-8 text-yellow-600" />
      default: 
        return <File className="w-8 h-8 text-gray-500" />
    }
  }

  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  const formatDate = (dateString) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric'
    })
  }

  const filteredDocuments = documents.filter(doc => {
    const matchesSearch = doc.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                         doc.description.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesSearch
  })

  const deleteDocument = (docId) => {
    if (window.confirm('Are you sure you want to delete this document?')) {
      setDocuments(prev => prev.filter(doc => doc.id !== docId))
    }
  }

  const handleFileUpload = (files) => {
    Array.from(files).forEach(file => {
      const fileId = `file-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
      
      // Create new document entry
      const newDoc = {
        id: fileId,
        name: file.name,
        type: getFileTypeFromExtension(file.name),
        size: file.size,
        folder: 'General',
        uploadDate: new Date().toISOString(),
        uploadedBy: 'Current User',
        description: `Uploaded file: ${file.name}`
      }
      
      setDocuments(prev => [newDoc, ...prev])
      console.log('✅ File uploaded:', file.name, 'Size:', file.size, 'Type:', file.type)
    })
  }

  const getFileTypeFromExtension = (filename) => {
    const ext = filename.split('.').pop().toLowerCase()
    const typeMap = {
      'pdf': 'pdf',
      'doc': 'word', 'docx': 'word',
      'xls': 'excel', 'xlsx': 'excel',
      'png': 'image', 'jpg': 'image', 'jpeg': 'image', 'gif': 'image', 'svg': 'image',
      'mp4': 'video', 'avi': 'video', 'mov': 'video',
      'mp3': 'audio', 'wav': 'audio',
      'zip': 'archive', 'rar': 'archive', '7z': 'archive'
    }
    return typeMap[ext] || 'file'
  }

  const handleUploadClick = () => {
    fileInputRef.current?.click()
  }

  const handleRetrieveDocuments = async () => {
    setIsRetrieving(true)
    
    // Simulate API call to retrieve documents from external sources
    setTimeout(() => {
      console.log('🔍 Retrieving documents from external sources...')
      // TODO: Add logic to retrieve documents from:
      // - Cloud storage (SharePoint, Google Drive, etc.)
      // - Document management systems
      // - AI knowledge bases
      // - External APIs
      
      setIsRetrieving(false)
      // For now, just log that the function was called
      alert('Retrieve Documents functionality will be implemented here.\n\nThis could connect to:\n- SharePoint/OneDrive\n- Google Drive\n- Document management systems\n- AI knowledge bases\n- External APIs')
    }, 2000)
  }

  const handleViewDocument = (doc) => {
    // For uploaded files, we would need to access the actual file data
    // For now, show document details in a modal or new tab
    if (doc.type === 'pdf' || doc.type === 'image') {
      // Simulate opening document viewer
      console.log('📖 Viewing document:', doc.name)
      alert(`Viewing Document: ${doc.name}\n\nType: ${doc.type}\nSize: ${formatFileSize(doc.size)}\nFolder: ${doc.folder}\nUploaded: ${formatDate(doc.uploadDate)}\n\nNote: Document viewer will be implemented to show actual file content.`)
    } else {
      alert(`Document: ${doc.name}\n\nThis file type (${doc.type}) requires downloading to view.\nUse the download button to save the file locally.`)
    }
  }

  const handleDownloadDocument = (doc) => {
    // For real implementation, this would download the actual file
    // For now, simulate the download process
    console.log('📥 Downloading document:', doc.name)
    
    // Create a mock download link
    const element = document.createElement('a')
    const file = new Blob([`Mock content for ${doc.name}\n\nThis is simulated file content.\nIn a real implementation, this would be the actual file data from your storage system.`], { type: 'text/plain' })
    element.href = URL.createObjectURL(file)
    element.download = doc.name
    document.body.appendChild(element)
    element.click()
    document.body.removeChild(element)
    
    // Clean up the blob URL
    URL.revokeObjectURL(element.href)
    
    console.log('✅ Download completed:', doc.name)
  }

  return (
    <div className="p-6">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Knowledge RAG Repository</h1>
        <p className="text-gray-600 mt-2">
          Centralized document repository for AI-powered retrieval and knowledge management.
        </p>
      </div>

      {/* Search and Controls */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0">
          <div className="relative">
            <Search className="w-5 h-5 absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" />
            <input
              type="text"
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-primary-500 w-80"
            />
          </div>
          
          <div className="flex gap-3">
            <button 
              className="btn btn-primary"
              onClick={handleUploadClick}
            >
              <Upload className="w-4 h-4 mr-2" />
              Upload Documents
            </button>
            <button 
              className="bg-green-600 text-white px-4 py-2 rounded-lg hover:bg-green-700 flex items-center gap-2 disabled:opacity-50"
              onClick={handleRetrieveDocuments}
              disabled={isRetrieving}
            >
              <RefreshCw className={`w-4 h-4 ${isRetrieving ? 'animate-spin' : ''}`} />
              {isRetrieving ? 'Retrieving...' : 'Retrieve Documents'}
            </button>
          </div>
        </div>
      </div>

      {/* Hidden file input */}
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.gif,.svg,.mp4,.avi,.mov,.mp3,.wav,.zip,.rar,.7z,.txt,.csv"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            handleFileUpload(e.target.files)
            e.target.value = '' // Reset input for future uploads
          }
        }}
      />

      {/* Documents Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
        {filteredDocuments.map(doc => (
          <div key={doc.id} className="bg-white border border-gray-200 rounded-lg p-4 hover:shadow-lg transition-shadow">
            <div className="flex items-start justify-between mb-3">
              <div className="flex items-center">
                {getFileIcon(doc.type)}
              </div>
              <div className="flex space-x-1">
                <button 
                  onClick={() => handleViewDocument(doc)}
                  className="text-gray-400 hover:text-blue-600 transition-colors"
                  title="View document"
                >
                  <Eye className="w-4 h-4" />
                </button>
                <button 
                  onClick={() => handleDownloadDocument(doc)}
                  className="text-gray-400 hover:text-green-600 transition-colors"
                  title="Download document"
                >
                  <Download className="w-4 h-4" />
                </button>
                <button 
                  onClick={() => deleteDocument(doc.id)}
                  className="text-red-400 hover:text-red-600 transition-colors"
                  title="Delete document"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>
            
            <h3 className="font-medium text-gray-900 text-sm mb-2 truncate" title={doc.name}>
              {doc.name}
            </h3>
            
            <p className="text-xs text-gray-600 mb-3 h-8 overflow-hidden">
              {doc.description}
            </p>
            
            <div className="flex items-center justify-between text-xs text-gray-500 mb-2">
              <span>{formatFileSize(doc.size)}</span>
              <span>{formatDate(doc.uploadDate)}</span>
            </div>
            
            <div className="flex items-center justify-between">
              <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded">
                {doc.folder}
              </span>
              <span className="text-xs text-gray-400">
                {doc.uploadedBy}
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* Empty State */}
      {filteredDocuments.length === 0 && (
        <div className="text-center py-12">
          <Database className="w-12 h-12 text-gray-400 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Documents Found</h3>
          <p className="text-gray-600 mb-4">
            {searchQuery 
              ? 'No documents match your search criteria.'
              : 'Start building your knowledge base by uploading documents.'
            }
          </p>
          {!searchQuery && (
            <button className="btn btn-primary">
              <Upload className="w-4 h-4 mr-2" />
              Upload Your First Document
            </button>
          )}
        </div>
      )}
    </div>
  )
}