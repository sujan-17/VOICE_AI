import React, { useState } from 'react';
import { BrowserRouter, Navigate, Route, Routes, useNavigate } from 'react-router-dom';

import { apiFetch } from './api';
import LoginPage from './pages/LoginPage';
import StaffPortal from './pages/StaffPortal';
import StudentPortal from './pages/StudentPortal';

function ProtectedRoute({ isAuthenticated, children }) {
  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }
  return children;
}

function RoleRoute({ user, role, children }) {
  if (!user) {
    return <Navigate to="/login" replace />;
  }
  if (user.role !== role) {
    return <Navigate to={user.role === 'staff' ? '/staff' : '/student'} replace />;
  }
  return children;
}

function AppRoutes({ authState, setAuthState }) {
  const navigate = useNavigate();

  const applyAuth = (data) => {
    const user = {
      email: data.email,
      full_name: data.full_name,
      role: data.role,
      role_id: data.role_id,
    };

    localStorage.setItem('voice-lab-token', data.access_token);
    localStorage.setItem('voice-lab-user', JSON.stringify(user));
    setAuthState({ token: data.access_token, user, loading: false, error: '' });
    navigate(user.role === 'staff' ? '/staff' : '/student', { replace: true });
  };

  const handleLogin = async ({ email, password }) => {
    setAuthState((previous) => ({ ...previous, loading: true, error: '' }));
    try {
      const data = await apiFetch('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      applyAuth(data);
    } catch (error) {
      setAuthState((previous) => ({ ...previous, loading: false, error: error.message }));
    }
  };

  const handleRegister = async (payload) => {
    setAuthState((previous) => ({ ...previous, loading: true, error: '' }));
    try {
      const data = await apiFetch('/auth/register', {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      applyAuth(data);
    } catch (error) {
      setAuthState((previous) => ({ ...previous, loading: false, error: error.message }));
    }
  };

  const handleGoogleLogin = async (googleToken) => {
    setAuthState((previous) => ({ ...previous, loading: true, error: '' }));
    try {
      const data = await apiFetch('/auth/google', {
        method: 'POST',
        body: JSON.stringify({ token: googleToken }),
      });
      applyAuth(data);
    } catch (error) {
      setAuthState((previous) => ({ ...previous, loading: false, error: error.message }));
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('voice-lab-token');
    localStorage.removeItem('voice-lab-user');
    setAuthState({ token: '', user: null, loading: false, error: '' });
    navigate('/login', { replace: true });
  };

  return (
    <Routes>
      <Route
        path="/login"
        element={
          <LoginPage
            onLogin={handleLogin}
            onRegister={handleRegister}
            onGoogleLogin={handleGoogleLogin}
            loading={authState.loading}
            error={authState.error}
          />
        }
      />
      <Route
        path="/student"
        element={
          <ProtectedRoute isAuthenticated={Boolean(authState.token)}>
            <RoleRoute user={authState.user} role="student">
              <StudentPortal token={authState.token} user={authState.user} onLogout={handleLogout} />
            </RoleRoute>
          </ProtectedRoute>
        }
      />
      <Route
        path="/staff"
        element={
          <ProtectedRoute isAuthenticated={Boolean(authState.token)}>
            <RoleRoute user={authState.user} role="staff">
              <StaffPortal token={authState.token} user={authState.user} onLogout={handleLogout} />
            </RoleRoute>
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to={authState.token ? (authState.user?.role === 'staff' ? '/staff' : '/student') : '/login'} replace />} />
    </Routes>
  );
}

function App() {
  const [authState, setAuthState] = useState(() => {
    const token = localStorage.getItem('voice-lab-token') || '';
    const rawUser = localStorage.getItem('voice-lab-user');
    return {
      token,
      user: rawUser ? JSON.parse(rawUser) : null,
      loading: false,
      error: '',
    };
  });

  return (
    <BrowserRouter>
      <AppRoutes authState={authState} setAuthState={setAuthState} />
    </BrowserRouter>
  );
}

export default App;
