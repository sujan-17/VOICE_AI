import React, { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';

function LoginPage({ onLogin, onRegister, onGoogleLogin, loading, error }) {
  const [mode, setMode] = useState('login');
  const [loginForm, setLoginForm] = useState({
    email: '',
    password: '',
  });
  const [registerForm, setRegisterForm] = useState({
    full_name: '',
    email: '',
    password: '',
    role: 'student',
    role_id: '',
    department: '',
  });

  const roleIdLabel = registerForm.role === 'staff' ? 'Staff ID' : 'Student ID';

  return (
    <div className="min-h-screen px-6 py-8 flex items-center justify-center app-shell">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="hero-orb hero-orb-a"></div>
        <div className="hero-orb hero-orb-b"></div>
        <div className="grid-overlay"></div>
      </div>

      <div className="w-full max-w-6xl relative z-10 grid lg:grid-cols-[1.05fr_0.95fr] gap-8">
        <section className="glass-panel login-hero p-10 lg:p-12">
          <p className="eyebrow">Welcome</p>
          <h1 className="mt-4 text-5xl font-semibold text-slate-900 leading-tight">
            Voice AI Lab Assistant
          </h1>
          <p className="mt-5 text-slate-600 text-lg leading-8 max-w-xl">
            A streamlined workspace for guided experiments, chat-based support, and lab evaluation.
          </p>
        </section>

        <section className="glass-panel p-8 lg:p-10">
          <div className="flex gap-3">
            <button className={`tab-chip ${mode === 'login' ? 'tab-chip-active-cyan' : ''}`} onClick={() => setMode('login')}>
              Login
            </button>
            <button className={`tab-chip ${mode === 'register' ? 'tab-chip-active-amber' : ''}`} onClick={() => setMode('register')}>
              Register
            </button>
          </div>

          {mode === 'login' ? (
            <>
              <h2 className="mt-6 text-2xl font-semibold text-slate-900">Sign in</h2>

              <form
                className="mt-8 space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  onLogin(loginForm);
                }}
              >
                <div>
                  <label className="field-label">Email</label>
                  <input
                    className="glass-input w-full px-4 py-3"
                    value={loginForm.email}
                    onChange={(event) => setLoginForm({ ...loginForm, email: event.target.value })}
                    placeholder="name@example.com"
                  />
                </div>
                <div>
                  <label className="field-label">Password</label>
                  <input
                    type="password"
                    className="glass-input w-full px-4 py-3"
                    value={loginForm.password}
                    onChange={(event) => setLoginForm({ ...loginForm, password: event.target.value })}
                    placeholder="Enter your password"
                  />
                </div>
                {error ? <p className="text-sm text-rose-600">{error}</p> : null}
                <button className="premium-button w-full py-3 text-sm tracking-[0.2em] uppercase" disabled={loading}>
                  {loading ? 'Signing In...' : 'Sign In'}
                </button>
              </form>

              <div className="mt-6">
                <p className="text-xs uppercase tracking-[0.18em] text-slate-500 mb-3">Or continue with Google</p>
                <GoogleLogin
                  onSuccess={(credentialResponse) => {
                    if (credentialResponse.credential) {
                      onGoogleLogin(credentialResponse.credential);
                    }
                  }}
                  onError={() => {
                    window.alert('Google login failed. Please try again.');
                  }}
                />
              </div>
            </>
          ) : (
            <>
              <h2 className="mt-6 text-2xl font-semibold text-slate-900">Create account</h2>

              <form
                className="mt-8 space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  onRegister(registerForm);
                }}
              >
                <div>
                  <label className="field-label">Full Name</label>
                  <input
                    className="glass-input w-full px-4 py-3"
                    value={registerForm.full_name}
                    onChange={(event) => setRegisterForm({ ...registerForm, full_name: event.target.value })}
                    placeholder="Enter full name"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="field-label">Role</label>
                    <select
                      className="glass-input w-full px-4 py-3"
                      value={registerForm.role}
                      onChange={(event) => setRegisterForm({ ...registerForm, role: event.target.value })}
                    >
                      <option value="student">Student</option>
                      <option value="staff">Staff</option>
                    </select>
                  </div>
                  <div>
                    <label className="field-label">{roleIdLabel}</label>
                    <input
                      className="glass-input w-full px-4 py-3"
                      value={registerForm.role_id}
                      onChange={(event) => setRegisterForm({ ...registerForm, role_id: event.target.value })}
                      placeholder={registerForm.role === 'staff' ? 'STAFF001' : 'STUDENT001'}
                    />
                  </div>
                </div>
                <div>
                  <label className="field-label">Email</label>
                  <input
                    className="glass-input w-full px-4 py-3"
                    value={registerForm.email}
                    onChange={(event) => setRegisterForm({ ...registerForm, email: event.target.value })}
                    placeholder="name@example.com"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="field-label">Password</label>
                    <input
                      type="password"
                      className="glass-input w-full px-4 py-3"
                      value={registerForm.password}
                      onChange={(event) => setRegisterForm({ ...registerForm, password: event.target.value })}
                      placeholder="Minimum 6 characters"
                    />
                  </div>
                  <div>
                    <label className="field-label">Department</label>
                    <input
                      className="glass-input w-full px-4 py-3"
                      value={registerForm.department}
                      onChange={(event) => setRegisterForm({ ...registerForm, department: event.target.value })}
                      placeholder="Computer Science"
                    />
                  </div>
                </div>
                {error ? <p className="text-sm text-rose-600">{error}</p> : null}
                <button className="premium-button w-full py-3 text-sm tracking-[0.2em] uppercase" disabled={loading}>
                  {loading ? 'Creating Account...' : 'Create Account'}
                </button>
              </form>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

export default LoginPage;
