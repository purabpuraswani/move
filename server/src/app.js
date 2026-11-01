import express from 'express';
import cors from 'cors';
import dotenv from 'dotenv';

import authRoutes from './routes/authRoutes.js';
import profileRoutes from './routes/profileRoutes.js';
import assessmentRoutes from './routes/assessmentRoutes.js';
import workflowRoutes from './routes/workflowRoutes.js';
import planRoutes from './routes/planRoutes.js';
import specialistRoutes from './routes/specialistRoutes.js';
import exerciseRoutes from './routes/exerciseRoutes.js';
import activityRoutes from './routes/activityRoutes.js';
import mealRoutes from './routes/mealRoutes.js';
import recoveryRoutes from './routes/recoveryRoutes.js';
import behaviourRoutes from './routes/behaviourRoutes.js';
import progressRoutes from './routes/progressRoutes.js';

dotenv.config();

const app = express();

// Middleware
app.use(cors());
app.use(express.json());

// Routes
app.use('/api/auth', authRoutes);
app.use('/api/profile', profileRoutes);
app.use('/api/assessments', assessmentRoutes);
app.use('/api/workflow', workflowRoutes);
app.use('/api/plans', planRoutes);
app.use('/api/specialists', specialistRoutes);
app.use('/api/exercises', exerciseRoutes);
app.use('/api/activity', activityRoutes);
app.use('/api/meals', mealRoutes);
app.use('/api/recovery', recoveryRoutes);
app.use('/api/behaviour', behaviourRoutes);
app.use('/api/progress', progressRoutes);

// Health check endpoint
app.get('/api/health', (req, res) => {
  res.json({ status: 'healthy', timestamp: new Date().toISOString() });
});

// Centralized error handler
app.use((err, req, res, next) => {
  console.error('Unhandled server error:', err);
  res.status(500).json({ error: 'Internal server error', message: err.message });
});

export default app;

