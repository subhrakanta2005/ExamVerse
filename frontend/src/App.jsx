import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import useAuthStore from './store/authStore'

// Auth pages
import LoginPage from './pages/LoginPage'
import SignupPage from './pages/SignupPage'
import ForgotPasswordPage from './pages/ForgotPasswordPage'
import ResetPasswordPage from './pages/ResetPasswordPage'

// Candidate pages
import CandidateDashboard from './pages/candidate/Dashboard'
import ExamInstructions from './pages/candidate/ExamInstructions'
import ExamRoom from './pages/candidate/ExamRoom'
import ResultPage from './pages/candidate/ResultPage'
import AttemptHistory from './pages/candidate/AttemptHistory'
import SyllabusExamPage   from "./pages/candidate/SyllabusExamPage";
import SyllabusResultPage from "./pages/candidate/SyllabusResultPage";

// Admin pages
import AdminDashboard from './pages/admin/Dashboard'
import AdminExams from './pages/admin/Exams'
import AdminExamEditor from './pages/admin/ExamEditor'
import AdminUsers from './pages/admin/Users'
import AdminResults from './pages/admin/Results'
import AdminAnalytics from './pages/admin/Analytics'
import AdminEvaluate from './pages/admin/Evaluate'
import SyllabusUpload from './pages/admin/SyllabusUpload'

// Guards
function PrivateRoute({ children }) {
  const { isAuthenticated } = useAuthStore()
  return isAuthenticated() ? children : <Navigate to="/login" replace />
}

function AdminRoute({ children }) {
  const { isAuthenticated, isAdmin } = useAuthStore()
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  if (!isAdmin()) return <Navigate to="/dashboard" replace />
  return children
}

function CandidateRoute({ children }) {
  const { isAuthenticated, isCandidate } = useAuthStore()
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  if (!isCandidate()) return <Navigate to="/admin" replace />
  return children
}

function RootRedirect() {
  const { isAuthenticated, isAdmin } = useAuthStore()
  if (!isAuthenticated()) return <Navigate to="/login" replace />
  return isAdmin() ? <Navigate to="/admin" replace /> : <Navigate to="/dashboard" replace />
}

export default function App() {
  return (
    <Routes>
      {/* Public */}
      <Route path="/" element={<RootRedirect />} />
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Candidate */}
      <Route path="/dashboard" element={<CandidateRoute><CandidateDashboard /></CandidateRoute>} />
      <Route path="/exam/:examId/instructions" element={<CandidateRoute><ExamInstructions /></CandidateRoute>} />
      <Route path="/exam/:examId/attempt/:attemptId" element={<CandidateRoute><ExamRoom /></CandidateRoute>} />
      <Route path="/result/:attemptId" element={<CandidateRoute><ResultPage /></CandidateRoute>} />
      <Route path="/history" element={<CandidateRoute><AttemptHistory /></CandidateRoute>} />
      <Route path="/exam/take"   element={<SyllabusExamPage />} />
      <Route path="/exam/result" element={<SyllabusResultPage />} />

      {/* Admin */}
      <Route path="/admin" element={<AdminRoute><AdminDashboard /></AdminRoute>} />
      <Route path="/admin/exams" element={<AdminRoute><AdminExams /></AdminRoute>} />
      <Route path="/admin/exams/new" element={<AdminRoute><AdminExamEditor /></AdminRoute>} />
      <Route path="/admin/exams/:examId/edit" element={<AdminRoute><AdminExamEditor /></AdminRoute>} />
      <Route path="/admin/users" element={<AdminRoute><AdminUsers /></AdminRoute>} />
      <Route path="/admin/results" element={<AdminRoute><AdminResults /></AdminRoute>} />
      <Route path="/admin/analytics" element={<AdminRoute><AdminAnalytics /></AdminRoute>} />
      <Route path="/admin/evaluate" element={<AdminRoute><AdminEvaluate /></AdminRoute>} />
      <Route path="/admin/syllabus" element={<AdminRoute><SyllabusUpload /></AdminRoute>} />

      {/* 404 */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
