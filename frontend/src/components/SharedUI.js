import React from 'react';

export function StatCard({ label, value, accent }) {
  return (
    <div className="glass-panel stat-card p-5 hover:-translate-y-1 transition-transform duration-300">
      <p className="text-xs uppercase tracking-[0.24em] text-slate-500">{label}</p>
      <p className={`mt-3 text-3xl font-semibold ${accent}`}>{value}</p>
    </div>
  );
}

export function TopBar({ user, onLogout, title, subtitle }) {
  return (
    <header className="glass-panel topbar-panel px-6 py-5 flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
      <div>
        <p className="eyebrow">{title}</p>
        <h1 className="text-3xl font-semibold text-slate-900 mt-2">{subtitle}</h1>
      </div>
      <div className="flex items-center gap-4">
        <div className="rounded-full px-4 py-2 bg-slate-50 border border-slate-200 shadow-sm">
          <p className="text-sm text-slate-900">{user.full_name}</p>
          <p className="text-xs uppercase tracking-[0.2em] text-slate-500">
            {user.role}{user.role_id ? ` • ${user.role_id}` : ''}
          </p>
        </div>
        <button className="premium-button px-5 py-3 text-xs uppercase tracking-[0.2em]" onClick={onLogout}>
          Logout
        </button>
      </div>
    </header>
  );
}
