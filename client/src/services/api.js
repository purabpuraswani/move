import axios from 'axios';

const api = axios.create({
  baseURL: '/api',
  headers: { 'Content-Type': 'application/json' }
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('movewell_token');
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('movewell_token');
      localStorage.removeItem('movewell_user');
      window.location.href = '/';
    }
    return Promise.reject(error);
  }
);

export default api;

// Auth
export const authService = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (name, email, password) => api.post('/auth/register', { name, email, password }),
  me: () => api.get('/auth/me')
};

// Profile
export const profileService = {
  get: () => api.get('/profile'),
  update: (data) => api.put('/profile', data),
  wellness: () => api.get('/profile/wellness')
};

// Assessments
export const assessmentService = {
  create: (data) => api.post('/assessments', data),
  getAll: () => api.get('/assessments'),
  getById: (id) => api.get(`/assessments/${id}`)
};

// Workflow
export const workflowService = {
  run: () => api.post('/workflow/run'),
  get: (id) => api.get(`/workflow/${id}`)
};

// Plans
export const planService = {
  current: () => api.get('/plans/current'),
  history: () => api.get('/plans/history'),
  getById: (id) => api.get(`/plans/${id}`),
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
  delete: (id) => api.delete(`/meals/${id}`)
};

// Recovery
export const recoveryService = {
  log: (data) => api.post('/recovery', data),
  getAll: () => api.get('/recovery')
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
