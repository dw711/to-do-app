import { Navigate, Route, Routes } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import BoardPage from './components/BoardPage';
import LoginPage from './pages/LoginPage';
import SignupPage from './pages/SignupPage';
import './App.css';

function ProtectedRoute() {
  const { token, loading } = useAuth();
  if (loading) return <div>Loading...</div>;
  return token ? <BoardPage /> : <Navigate to="/login" replace />;
}

function PublicRoute({ children }) {
  const { token, loading } = useAuth();
  if (loading) return <div>Loading...</div>;
  return token ? <Navigate to="/board" replace /> : children;
}

export default function App() {
  return <AuthProvider><Routes>
    <Route path="/login" element={<PublicRoute><LoginPage /></PublicRoute>} />
    <Route path="/signup" element={<PublicRoute><SignupPage /></PublicRoute>} />
    <Route path="/board" element={<ProtectedRoute />} />
    <Route path="/" element={<Navigate to="/board" replace />} />
    <Route path="*" element={<Navigate to="/board" replace />} />
  </Routes></AuthProvider>;
}
