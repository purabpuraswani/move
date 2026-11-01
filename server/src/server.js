import app from './app.js';
import { initializeDatabase } from './database/initialize.js';

const PORT = process.env.PORT || 3001;

// Initialize SQLite database schema
initializeDatabase();

app.listen(PORT, () => {
  console.log(`🚀 MoveWell AI Server running on http://localhost:${PORT}`);
  console.log(`📡 Health check at http://localhost:${PORT}/api/health`);
});

