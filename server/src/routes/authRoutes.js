import express from 'express';
import bcrypt from 'bcryptjs';
import jwt from 'jsonwebtoken';
import { v4 as uuidv4 } from 'uuid';
import { getDb } from '../database/connection.js';
import { authenticateToken } from '../middleware/auth.js';

const router = express.Router();
const JWT_SECRET = process.env.JWT_SECRET || 'movewell_jwt_secret_key_2024_secure';

// Register
router.post('/register', async (req, res) => {
  const { name, email, password } = req.body;
  if (!name || !email || !password) {
    return res.status(400).json({ error: 'Name, email, and password are required' });
  }

  const db = getDb();
  try {
    const existing = db.prepare('SELECT id FROM users WHERE email = ?').get(email.toLowerCase());
    if (existing) {
      return res.status(409).json({ error: 'User with this email already exists' });
    }

    const userId = uuidv4();
    const passwordHash = await bcrypt.hash(password, 10);

    const insertUser = db.transaction(() => {
      db.prepare(`
        INSERT INTO users (id, name, email, password_hash)
        VALUES (?, ?, ?, ?)
      `).run(userId, name.trim(), email.toLowerCase().trim(), passwordHash);

      // Create default profile
      db.prepare(`
        INSERT INTO user_profiles (id, user_id, onboarding_completed)
        VALUES (?, ?, 0)
      `).run(uuidv4(), userId);

      // Create initial health screening with UNKNOWN
      db.prepare(`
        INSERT INTO health_screenings (id, user_id)
        VALUES (?, ?)
      `).run(uuidv4(), userId);
    });

    insertUser();

    const token = jwt.sign({ userId, email: email.toLowerCase() }, JWT_SECRET, { expiresIn: '7d' });
    res.status(201).json({
      user: { id: userId, name: name.trim(), email: email.toLowerCase().trim(), onboarding_completed: 0 },
      token
    });
  } catch (err) {
    console.error('Registration error:', err);
    res.status(500).json({ error: 'Failed to register user' });
  }
});

// Login
router.post('/login', async (req, res) => {
  const { email, password } = req.body;
  if (!email || !password) {
    return res.status(400).json({ error: 'Email and password are required' });
  }

  const db = getDb();
  try {
    const user = db.prepare('SELECT * FROM users WHERE email = ?').get(email.toLowerCase().trim());
    if (!user) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }

    const valid = await bcrypt.compare(password, user.password_hash);
    if (!valid) {
      return res.status(401).json({ error: 'Invalid email or password' });
    }

    const profile = db.prepare('SELECT onboarding_completed FROM user_profiles WHERE user_id = ?').get(user.id);
    const token = jwt.sign({ userId: user.id, email: user.email }, JWT_SECRET, { expiresIn: '7d' });

    res.json({
      user: {
        id: user.id,
        name: user.name,
        email: user.email,
        onboarding_completed: profile ? profile.onboarding_completed : 0
      },
      token
    });
  } catch (err) {
    console.error('Login error:', err);
    res.status(500).json({ error: 'Failed to log in' });
  }
});

// Me
router.get('/me', authenticateToken, (req, res) => {
  const db = getDb();
  try {
    const user = db.prepare('SELECT id, name, email, created_at FROM users WHERE id = ?').get(req.userId);
    if (!user) return res.status(404).json({ error: 'User not found' });

    const profile = db.prepare('SELECT * FROM user_profiles WHERE user_id = ?').get(req.userId);
    res.json({ user: { ...user, onboarding_completed: profile?.onboarding_completed || 0 }, profile });
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch user data' });
  }
});

export default router;

