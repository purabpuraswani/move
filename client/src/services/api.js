import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:3001/api';

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json'
  }
});

// Attach JWT token to requests if available
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('movewell_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Authentication
export const authService = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (name, email, password) => api.post('/auth/register', { name, email, password }),
  getMe: () => api.get('/auth/me')
};

// Profile & Onboarding
export const profileService = {
  get: () => api.get('/profile'),
  update: (data) => api.post('/profile', data),
  getScreening: () => api.get('/profile/screening'),
  updateScreening: (data) => api.post('/profile/screening', data)
};

// Movement Assessments
export const assessmentService = {
  create: (data) => api.post('/assessments', data),
  getAll: () => api.get('/assessments'),
  getHistory: (type) => api.get(`/assessments/history/${type}`),
  getSummary: () => api.get('/assessments/summary')
};

// Orchestrated Workflow
export const workflowService = {
  run: () => api.post('/workflow/run'),
  getById: (id) => api.get(`/workflow/${id}`)
};

// Health Plans
export const planService = {
  getLatest: () => api.get('/plans/latest'),
  getByDate: (date) => api.get(`/plans/date/${date}`),
  getScore: () => api.get('/plans/score'),
  completeActivity: (activityId, notes) => api.post('/activity/complete', { plan_activity_id: activityId, notes })
};

// Specialists
export const specialistService = {
  getAll: () => api.get('/specialists'),
  getByName: (name) => api.get(`/specialists/${name}`)
};

// Exercises
export const exerciseService = {
  getAll: () => api.get('/exercises'),
  getById: (id) => api.get(`/exercises/${id}`),
  complete: (id, data) => api.post(`/exercises/${id}/complete`, data)
};

// Activity
export const activityService = {
  log: (data) => api.post('/activity', data),
  getAll: () => api.get('/activity'),
  complete: (data) => api.post('/activity/complete', data)
};

// Meals
export const mealService = {
  log: (data) => api.post('/meals', data),
  getAll: () => api.get('/meals'),
  delete: (id) => api.delete(`/meals/${id}`),
  chat: (data) => api.post('/meals/chat', data)
};

// Recovery
export const recoveryService = {
  log: (data) => api.post('/recovery', data),
  getAll: () => api.get('/recovery'),
  chat: (data) => api.post('/recovery/chat', data)
};

// Behaviour
export const behaviourService = {
  log: (data) => api.post('/behaviour', data),
  getAll: () => api.get('/behaviour')
};

// Progress
export const progressService = {
  get: () => api.get('/progress'),
  trends: () => api.get('/progress/trends')
};

export default api;
