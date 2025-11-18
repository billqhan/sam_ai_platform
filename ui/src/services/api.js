import axios from 'axios';

// If VITE_API_BASE_URL is set (production API Gateway), use it as-is without /api prefix
// Otherwise fall back to VITE_API_URL or local /api proxy
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL 
  ? import.meta.env.VITE_API_BASE_URL
  : (import.meta.env.VITE_API_URL || '/api');

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor for adding auth tokens
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

export const workflowApi = {
  // Trigger workflow steps
  triggerDownload: () => api.post('/workflow/download'),
  triggerProcessing: (params) => api.post('/workflow/process', params),
  triggerMatching: (params) => api.post('/workflow/match', params),
  triggerReports: () => api.post('/workflow/reports'),
  triggerNotification: () => api.post('/workflow/notify'),
  
  // Generate automatic workflow report
  generateAutoReport: (data) => api.post('/workflow/auto-report', data),
  
  // Get workflow status
  getStatus: () => api.get('/workflow/status'),
  getHistory: (limit = 10) => api.get(`/workflow/history?limit=${limit}`),
};

export const opportunitiesApi = {
  // Get opportunities
  getAll: (params) => api.get('/opportunities', { params }),
  getById: (id) => api.get(`/opportunities/${id}`),
  getByDate: (date) => api.get(`/opportunities/date/${date}`),
  
  // Search and filter
  search: (query) => api.get('/opportunities/search', { params: query }),
  getCategories: () => api.get('/opportunities/categories'),
  getAgencies: () => api.get('/opportunities/agencies'),
};

export const matchesApi = {
  // Get matches
  getAll: (params) => api.get('/matches', { params }),
  getById: (id) => api.get(`/matches/${id}`),
  getByOpportunity: (opportunityId) => api.get(`/matches/opportunity/${opportunityId}`),
  
  // Match operations
  triggerMatching: () => api.post('/matches/trigger'),
  rerunMatch: (opportunityId) => api.post(`/matches/rerun/${opportunityId}`),
  updateScore: (matchId, score) => api.patch(`/matches/${matchId}/score`, { score }),
  addNote: (matchId, note) => api.post(`/matches/${matchId}/notes`, { note }),
};

export const reportsApi = {
  // Get reports
  getLatest: () => api.get('/reports/latest'),
  getByDate: (date) => api.get(`/reports/date/${date}`),
  getHistory: (params) => api.get('/reports/history', { params }),
  
  // Generate reports
  generateWebReport: (date) => api.post('/reports/web', { date }),
  generateUserReport: (matchId) => api.post('/reports/user', { matchId }),
  
  // Download reports
  downloadWebReport: (reportId) => api.get(`/reports/web/${reportId}/download`, { responseType: 'blob' }),
  downloadUserReport: (reportId) => api.get(`/reports/user/${reportId}/download`, { responseType: 'blob' }),
};

export const dashboardApi = {
  // Get dashboard data
  getMetrics: () => api.get('/dashboard/metrics'),
  getChartData: (type, period = '7d') => api.get(`/dashboard/charts/${type}?period=${period}`),
  getRecentActivity: (limit = 10) => api.get(`/dashboard/activity?limit=${limit}`),
  getTopMatches: (limit = 5) => api.get(`/dashboard/top-matches?limit=${limit}`),
};

export const settingsApi = {
  // Get settings
  getAll: () => api.get('/settings'),
  get: (key) => api.get(`/settings/${key}`),
  
  // Update settings
  update: (settings) => api.put('/settings', settings),
  updateKey: (key, value) => api.put(`/settings/${key}`, { value }),
  
  // Company profiles
  getProfiles: () => api.get('/settings/profiles'),
  updateProfile: (profileId, data) => api.put(`/settings/profiles/${profileId}`, data),
};

export const proposalApi = {
  // Get proposals and matches
  getProposals: () => api.get('/proposals'),
  getProposal: (id) => api.get(`/proposals/${id}`),
  getMatches: () => api.get('/matches'),
  
  // Proposal CRUD operations
  createProposal: (data) => api.post('/proposals', data),
  updateProposal: (id, data) => api.put(`/proposals/${id}`, data),
  deleteProposal: (id) => api.delete(`/proposals/${id}`),
  
  // Proposal workflow
  submitProposal: (id) => api.post(`/proposals/${id}/submit`),
  approveProposal: (id) => api.post(`/proposals/${id}/approve`),
  rejectProposal: (id, reason) => api.post(`/proposals/${id}/reject`, { reason }),
  
  // Proposal sections
  updateSection: (proposalId, section, data) => api.put(`/proposals/${proposalId}/sections/${section}`, data),
  getSection: (proposalId, section) => api.get(`/proposals/${proposalId}/sections/${section}`),
};

export default api;
