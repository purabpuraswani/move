import { BrowserRouter, Routes, Route } from "react-router-dom";

// Registers all Movement Demonstrations (movementDemos/content.js) once, for
// its side effect, before any assessment panel or exercise card looks one up
// via movementDemos/registry.js's getMovementDemo(). Imported here (the app
// root) rather than from registry.js itself to avoid a circular import,
// since content.js imports registerMovementDemo from registry.js.
import "./movementDemos/content.js";

import RequireAuth from "./components/RequireAuth";
import ScrollToTop from "./components/ScrollToTop";

import LandingPage from "./pages/LandingPage";
import SignupPage from "./pages/SignupPage";
import LoginPage from "./pages/LoginPage";
import ForgotPasswordPage from "./pages/ForgotPasswordPage";
import ResetPasswordPage from "./pages/ResetPasswordPage";

import OnboardingPage from "./pages/OnboardingPage";
import Dashboard from "./pages/Dashboard";
import AssessmentPage from "./pages/AssessmentPage";
import HistoryPage from "./pages/HistoryPage";
import ReportsPage from "./pages/ReportsPage";
import ReportReviewPage from "./pages/ReportReviewPage";
import PlanPage from "./pages/PlanPage";
import ProgressPage from "./pages/ProgressPage";
import ExercisePage from "./pages/ExercisePage";
import DashboardInternalPage from "./pages/DashboardInternalPage";
import SpecialistDetailPage from "./pages/SpecialistDetailPage";

// DEPRECATED. The legacy guidance path (Wellness Guide / Care Navigator,
// backend/agents/ + /api/guidance). It is kept reachable so an existing
// bookmark does not break, but it is no longer part of the MoveWell journey:
// the plan a user is given comes from the Orchestrator via /plan. Nothing in
// the primary flow links here.
import GuidancePage from "./pages/GuidancePage";

function App() {

  return (
    <BrowserRouter>

      <ScrollToTop />

      <Routes>

        {/* Open to anyone. */}

        <Route
          path="/"
          element={<LandingPage />}
        />

        <Route
          path="/signup"
          element={<SignupPage />}
        />

        <Route
          path="/login"
          element={<LoginPage />}
        />

        <Route
          path="/forgot-password"
          element={<ForgotPasswordPage />}
        />

        <Route
          path="/reset-password"
          element={<ResetPasswordPage />}
        />

        {/* Everything below needs an account. RequireAuth sends a signed-out
            visitor to the sign-in page and remembers where they were going,
            instead of rendering a screen whose every request is about to fail.

            The real protection is on the API: each of these screens reads data
            the backend releases only to the owner of the token on the request.
            Hiding a route in the browser protects nothing by itself. */}

        <Route
          path="/dashboard"
          element={
            <RequireAuth>
              <Dashboard />
            </RequireAuth>
          }
        />

        <Route
          path="/onboarding"
          element={
            <RequireAuth>
              <OnboardingPage />
            </RequireAuth>
          }
        />

        <Route
          path="/assessment"
          element={
            <RequireAuth>
              <AssessmentPage />
            </RequireAuth>
          }
        />

        <Route
          path="/assess"
          element={
            <RequireAuth>
              <AssessmentPage />
            </RequireAuth>
          }
        />

        <Route
          path="/history"
          element={
            <RequireAuth>
              <HistoryPage />
            </RequireAuth>
          }
        />

        <Route
          path="/reports"
          element={
            <RequireAuth>
              <ReportsPage />
            </RequireAuth>
          }
        />

        {/* The review screen for one report. Its own route so a half-finished
            review can be returned to directly. */}
        <Route
          path="/reports/:reportId"
          element={
            <RequireAuth>
              <ReportReviewPage />
            </RequireAuth>
          }
        />

        {/* The plan, and the loop around it. These two are the MoveWell
            journey's destination: /plan is what the Orchestrator produced
            after the Safety Gate, /progress is what changed and why. */}
        <Route
          path="/plan"
          element={
            <RequireAuth>
              <PlanPage />
            </RequireAuth>
          }
        />

        <Route
          path="/progress"
          element={
            <RequireAuth>
              <ProgressPage />
            </RequireAuth>
          }
        />

        {/* Performing one exercise from the plan. This is what makes
            src/exerciseAssessment/ reachable: without a route there was no
            way for a user to run those engines, and no exercise result was
            ever produced for the Progress Agent to read. */}
        <Route
          path="/exercise/:exerciseId"
          element={
            <RequireAuth>
              <ExercisePage />
            </RequireAuth>
          }
        />

        {/* Dedicated Specialist screens for the 6 specialist agents:
            exercise, physio, nutrition, recovery, behaviour, safety */}
        <Route
          path="/specialist/:specialistType"
          element={
            <RequireAuth>
              <SpecialistDetailPage />
            </RequireAuth>
          }
        />

        <Route
          path="/specialists"
          element={
            <RequireAuth>
              <SpecialistDetailPage />
            </RequireAuth>
          }
        />

        {/* DEPRECATED, kept only so an existing bookmark still resolves.
            Superseded by /plan. Not linked from anywhere in the app. */}
        <Route
          path="/guidance"
          element={
            <RequireAuth>
              <GuidancePage />
            </RequireAuth>
          }
        />

        {/* Internal/staff-only observability dashboard. Real access
            control is the backend's require_staff_user dependency -- this
            route just needs the user to be signed in at all. */}
        <Route
          path="/internal/dashboard"
          element={
            <RequireAuth>
              <DashboardInternalPage />
            </RequireAuth>
          }
        />

        <Route
          path="/dashboard/internal"
          element={
            <RequireAuth>
              <DashboardInternalPage />
            </RequireAuth>
          }
        />

        {/* A mistyped address should not render an empty page. */}
        <Route
          path="*"
          element={<LandingPage />}
        />

      </Routes>

    </BrowserRouter>
  );
}


export default App;
