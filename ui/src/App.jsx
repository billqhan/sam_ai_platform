import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Opportunities from './pages/Opportunities'
import OpportunityDetail from './pages/OpportunityDetail'
import Matches from './pages/Matches'
import Workflow from './pages/Workflow'
import Reports from './pages/Reports'
import Settings from './pages/Settings'
import Proposals from './pages/Proposals'
import Prompts from './pages/Prompts'
import Compliance from './pages/Compliance'
import KnowledgeRAG from './pages/KnowledgeRAG'
import TestPage from './pages/TestPage'

function App() {
  return (
    <Router>
      <Layout>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/opportunities" element={<Opportunities />} />
          <Route path="/opportunities/:id" element={<OpportunityDetail />} />
          <Route path="/matches" element={<Matches />} />
          <Route path="/workflow" element={<Workflow />} />
          <Route path="/proposals" element={<Proposals />} />
          <Route path="/prompts" element={<Prompts />} />
          <Route path="/compliance" element={<Compliance />} />
          <Route path="/knowledge" element={<KnowledgeRAG />} />
          <Route path="/reports" element={<Reports />} />
          <Route path="/settings" element={<Settings />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </Layout>
    </Router>
  )
}

export default App
