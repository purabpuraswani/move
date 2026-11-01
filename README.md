# MoveWell AI — Multi-Specialist Wellness & Movement Intelligence Platform

MoveWell AI is a full-stack, multi-specialist wellness management platform powered by real-time computer vision kinematics (**MoveNet SinglePose Lightning** via TensorFlow.js), a six-specialist clinical reasoning pipeline, and an authentic SQLite database with zero fabricated metrics.

Designed with a modern Stitch-inspired dark forest-green visual identity, MoveWell AI provides an end-to-end journey: from clinical onboarding and camera-based movement assessments to personalized multi-domain intervention plans and real-time exercise repetition tracking.

---

## 🌟 Key Features & Architecture

### 1. Six Specialist Intelligence Engines
Six connected specialist services analyze one common **Unified User Wellness Profile** to coordinate an evidence-based **Unified Health Plan**:
- 🩺 **Physiotherapy Specialist**: Range of motion, scapular rhythm symmetry, unilateral balance stability, and corrective therapeutic exercises.
- 🥗 **Nutrition Specialist**: Macro/micronutrient targets, anti-inflammatory protocols, hydration, and meal adherence tracking.
- 🧠 **Behaviour Specialist**: Habit loops, micro-commitments, consistency scoring, and adherence barriers.
- 🌙 **Wellness & Recovery Specialist**: Sleep hygiene, active recovery routines, stress modulation, and central nervous system fatigue monitoring.
- 🏋️‍♂️ **Exercise & Physical Activity Specialist**: Functional strength conditioning, progressive overload, and movement frequency.
- 📈 **Progress & Analytics Specialist**: Longitudinal kinematics, adherence trends, score progression, and reassessment scheduling.

### 2. MoveNet Computer Vision Kinematics
- **17-Keypoint Pose Tracking**: Real-time pose estimation running entirely client-side using `@tensorflow-models/pose-detection` (MoveNet SinglePose Lightning) on WebGL/Wasm backends.
- **Two Standardized Clinical Movement Assessments**:
  1. **Bilateral Shoulder Raise (Flexion & Abduction)**: Calculates left and right arm elevation angles relative to torso vector, detects peak range of motion (ROM target: 180°), and computes scapular rhythm asymmetry delta.
  2. **One-Leg Stand Balance (Equilibrium & Stability)**: Detects unilateral foot elevation, measures sustained balance duration, and detects balance loss or ground contacts.
- **Exercise Form Mirror & Repetition Counter**: Joint-angle biomechanics state machine (Eccentric vs Concentric phases) with audio-visual cues and rep counting for prescribed physiotherapy movements.

### 3. Media & Exercise Catalogue
Includes photorealistic male human reference demonstration guides and clear vector illustrations:
- `shoulder-raise-assessment.jpg` — Photorealistic assessment reference guide for Bilateral Shoulder Raise.
- `one-leg-stand-assessment.jpg` — Photorealistic assessment reference guide for Single-Leg Balance.
- `glute-bridge.jpg` & `.svg` — Floor bridge pelvic elevation technique.
- `shoulder-wall-slide.jpg` & `.svg` — Wall slide scapular upward rotation technique.
- `sit-to-stand.jpg` & `.svg` — Chair squat functional lower-body strength.
- `standing-side-leg-raise.jpg` & `.svg` — Hip abductor & gluteus medius stabilization.
- `single-leg-balance.jpg` & `.svg` — Proprioceptive ankle and knee stability.

### 4. Authentic SQLite Persistence (No Fabricated Data)
- Every metric, streak, confidence score, and completion percentage is calculated strictly from SQLite records (`server/data/movewell.db`).
- Unmeasured parameters display clear, honest states (`NOT ASSESSED`, `NOT LOGGED`, `UNKNOWN`) rather than hardcoded mock percentages.

---

## 📋 System Prerequisites

Before running the application, ensure you have:
- **Node.js**: `v18.0.0` or higher (tested on Node v20 and v26).
- **npm**: `v9.0.0` or higher (or `pnpm` / `yarn`).
- **Webcam**: Required for real-time MoveNet movement assessment and exercise tracking.
- **Modern Web Browser**: Google Chrome, Microsoft Edge, Brave, or Mozilla Firefox with hardware acceleration enabled for optimal MoveNet FPS.

---

## 🚀 Quick Start Guide (How to Run)

### Option A: Standard Step-by-Step Setup (Recommended)

#### 1. Clone the Repository
```bash
git clone https://github.com/purabpuraswani/move.git
cd move
```

#### 2. Setup and Start the Backend Server
```bash
# Navigate to the server folder
cd server

# Install backend dependencies
npm install

# Seed the SQLite database with exercises, specialists, and sample users
npm run seed

# Start the Express API server (runs on http://localhost:3001)
npm run dev
```

> **Note**: The backend automatically initializes `server/data/movewell.db`.

#### 3. Setup and Start the Frontend Client
Open a **second terminal window**:
```bash
# Navigate to the client folder
cd client

# Install frontend dependencies
npm install

# Start the Vite development server (runs on http://localhost:5173)
npm run dev
```

#### 4. Open in Browser
Open your browser and navigate to:
```
http://localhost:5173
```

---

### Option B: Concurrent Setup from Root

If you have installed dependencies at the root directory:
```bash
# 1. Install root dependencies
npm install

# 2. Setup server & client dependencies automatically
npm run setup

# 3. Seed database
npm run seed

# 4. Start both backend and frontend concurrently
npm run dev
```

---

## 👥 Demo Accounts & Authentication

You can log in with the pre-seeded account or create a new user:

| Account Type | Email | Password | Role / State |
| :--- | :--- | :--- | :--- |
| **Demo User** | `alex@movewell.ai` | `password123` | Pre-configured profile with sample history |
| **New User** | Any valid email | Any password (min 6 chars) | Fresh onboarding & baseline assessments |

You can also click **"Demo Login"** on the login screen for instant one-click access.

---

## 🔄 User Journey Walkthrough

1. **Authentication & Profile Setup**:
   - Register or log in.
   - Complete the Onboarding Health Screen (Lifestyle, physical limitations, joint pain, health goals).
2. **MoveNet AI Movement Assessment**:
   - Navigate to **Movement Assessment** (`/assessment`).
   - Position yourself 2–3 meters back from the webcam until your upper body and arms are visible.
   - Side-by-side reference photographs demonstrate proper execution for each test.
   - Click **Start Camera Assessment** for:
     - **Test 1**: Bilateral Shoulder Raise (measures peak elevation angle and scapular asymmetry).
     - **Test 2**: One-Leg Stand Balance (measures single-leg hold stability).
   - Review calibrated results and click **Save Assessment Record** to commit them to SQLite.
3. **Six Specialist Consultation & Plan Generation**:
   - Navigate to **Specialists** (`/specialists`) or **My Plan** (`/plan`).
   - Click **Generate / Refresh Health Plan**. The backend orchestrates the 6 specialists, analyzes profile gaps and assessment results, and synthesizes target recommendations.
   - Explore specialist tabs: Physiotherapy, Nutrition, Behaviour, Recovery, Exercise, Progress.
4. **Physiotherapy Exercise & AI Repetition Mirror**:
   - Open a prescribed physiotherapy exercise (e.g. *Glute Bridge* or *Shoulder Wall Slide*).
   - Click **Start AI Movement Session**.
   - MoveNet tracks your joint kinematics in real time, validating repetition completion, posture depth, and session hold time.
   - Save session to automatically update adherence metrics and activity logs.
5. **Progress & Longitudinal Tracking**:
   - Navigate to **Progress** (`/progress`) to inspect true historical compliance, assessment timeline, and specialist milestone completions.

---

## 📁 Repository Structure

```
move/
├── client/                           # React + Vite Frontend
│   ├── public/
│   │   └── exercises/images/         # Assessment & exercise demonstration photos
│   │       ├── shoulder-raise-assessment.jpg
│   │       ├── one-leg-stand-assessment.jpg
│   │       ├── glute-bridge.jpg (.svg)
│   │       ├── shoulder-wall-slide.jpg (.svg)
│   │       ├── sit-to-stand.jpg (.svg)
│   │       ├── standing-side-leg-raise.jpg (.svg)
│   │       └── single-leg-balance.jpg (.svg)
│   ├── src/
│   │   ├── assessment/               # MoveNet pose engine & assessment protocols
│   │   │   ├── pose/                 # Pose detector singleton & camera stream
│   │   │   ├── tests/                # Shoulder raise & balance algorithms
│   │   │   └── hooks/                # usePoseEngine, useTestRunner
│   │   ├── components/               # Navbar, ExerciseTrackingCard, UI widgets
│   │   ├── context/                  # AuthContext, WellnessContext
│   │   ├── pages/                    # Dashboard, Assessment, Plan, Specialists, Progress
│   │   └── services/                 # API client utilities
│   ├── package.json
│   └── vite.config.js
│
├── server/                           # Express + SQLite Backend
│   ├── data/                         # SQLite database file (movewell.db)
│   ├── src/
│   │   ├── database/                 # SQLite schema, migrations & seed scripts
│   │   ├── middleware/               # JWT authentication middleware
│   │   ├── routes/                   # Auth, profile, assessment, plan, activity routes
│   │   ├── services/                 # 6 Specialist logic & workflow orchestrator
│   │   │   ├── physiotherapySpecialist.js
│   │   │   ├── nutritionSpecialist.js
│   │   │   ├── behaviourSpecialist.js
│   │   │   ├── recoverySpecialist.js
│   │   │   ├── exerciseSpecialist.js
│   │   │   ├── progressSpecialist.js
│   │   │   └── planOrchestrator.js
│   │   └── server.js                 # Express server entry point
│   └── package.json
│
├── .gitignore
├── package.json                      # Root workspace scripts
└── README.md
```

---

## 🛠️ API Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/auth/register` | Register a new user |
| `POST` | `/api/auth/login` | Login and receive JWT token |
| `GET` | `/api/profile` | Retrieve authenticated user profile |
| `PUT` | `/api/profile` | Update user profile & health screen |
| `GET` | `/api/assessments` | Get assessment history for user |
| `POST` | `/api/assessments` | Save new MoveNet assessment record |
| `GET` | `/api/plan` | Get current active health plan |
| `POST` | `/api/plan/generate` | Run 6 specialists and generate new plan |
| `GET` | `/api/activities` | List exercise and activity catalogue |
| `POST` | `/api/activities/log` | Record completed exercise rep session |
| `GET` | `/api/progress` | Calculate authentic progress metrics |

---

## ❓ Troubleshooting & FAQs

- **Camera permissions blocked?**
  - Click the lock/tune icon in your browser URL bar (e.g. `chrome://settings/content/camera`), select **Allow** for `http://localhost:5173`, and reload the page.
- **MoveNet Model loading slowly?**
  - First-time loading downloads the lightweight MoveNet SinglePose model (`~12MB`). Subsequent runs load instantly from the browser cache.
- **Port 3001 or 5173 already in use?**
  - Server port can be configured via `PORT=3002 npm run dev` in `server/`.
  - Client proxy automatically points to the backend configured in `client/vite.config.js`.
- **Reset database to clean state?**
  - Run `cd server && npm run seed`.

---

## 📄 License
ISC License. Built for wellness intelligence and computer-vision powered human movement science.
