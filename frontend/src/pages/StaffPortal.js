import React, { useEffect, useState } from 'react';

import { apiFetch } from '../api';
import { StatCard, TopBar } from '../components/SharedUI';

const EMPTY_FORM = {
  slug: '',
  title: '',
  objective: '',
  steps: 'Step 1\nStep 2\nStep 3',
};

function StaffPortal({ token, user, onLogout }) {
  const [dashboard, setDashboard] = useState(null);
  const [experiments, setExperiments] = useState([]);
  const [selectedExperiment, setSelectedExperiment] = useState(null);
  const [studentDetail, setStudentDetail] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const loadStaffData = async () => {
    const [dashboardData, experimentsData] = await Promise.all([
      apiFetch('/staff/dashboard', { token }),
      apiFetch('/experiments', { token }),
    ]);
    setDashboard(dashboardData);
    setExperiments(experimentsData);

    if (!selectedExperiment && experimentsData.length > 0) {
      const defaultExperiment = experimentsData[0];
      setSelectedExperiment(defaultExperiment.slug);
      setForm({
        slug: defaultExperiment.slug,
        title: defaultExperiment.title,
        objective: defaultExperiment.objective,
        steps: (defaultExperiment.steps || []).join('\n'),
      });
    }
  };

  useEffect(() => {
    Promise.all([
      apiFetch('/staff/dashboard', { token }),
      apiFetch('/experiments', { token }),
    ])
      .then(([dashboardData, experimentsData]) => {
        setDashboard(dashboardData);
        setExperiments(experimentsData);

        if (experimentsData.length > 0) {
          const defaultExperiment = experimentsData[0];
          setSelectedExperiment((current) => current || defaultExperiment.slug);
          setForm((current) => {
            if (current.slug || selectedExperiment) {
              return current;
            }
            return {
              slug: defaultExperiment.slug,
              title: defaultExperiment.title,
              objective: defaultExperiment.objective,
              steps: (defaultExperiment.steps || []).join('\n'),
            };
          });
        }
      })
      .catch((requestError) => {
        console.error(requestError);
        setError(requestError.message);
      });
  }, [token, selectedExperiment]);

  const selectExperiment = (slug) => {
    setSelectedExperiment(slug);
    const experiment = experiments.find((item) => item.slug === slug) || dashboard?.experiments?.find((item) => item.slug === slug);
    if (!experiment) {
      setForm(EMPTY_FORM);
      return;
    }

    setForm({
      slug: experiment.slug,
      title: experiment.title,
      objective: experiment.objective,
      steps: (experiment.steps || []).join('\n'),
    });
  };

  const handleCreate = async () => {
    setSaving(true);
    setMessage('');
    setError('');

    try {
      await apiFetch('/staff/experiments', {
        method: 'POST',
        token,
        body: JSON.stringify({
          slug: form.slug.trim(),
          title: form.title.trim(),
          objective: form.objective.trim(),
          steps: form.steps.split('\n').map((step) => step.trim()).filter(Boolean),
        }),
      });
      setMessage('Experiment created successfully.');
      setForm(EMPTY_FORM);
      setSelectedExperiment(null);
      await loadStaffData();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async () => {
    if (!selectedExperiment) return;

    setSaving(true);
    setMessage('');
    setError('');

    try {
      await apiFetch(`/staff/experiments/${selectedExperiment}`, {
        method: 'PUT',
        token,
        body: JSON.stringify({
          title: form.title.trim(),
          objective: form.objective.trim(),
          steps: form.steps.split('\n').map((step) => step.trim()).filter(Boolean),
        }),
      });
      setMessage('Experiment updated successfully.');
      await loadStaffData();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!selectedExperiment) return;
    const confirmed = window.confirm(`Delete experiment "${selectedExperiment}"? This only works if no student sessions use it yet.`);
    if (!confirmed) return;

    setSaving(true);
    setMessage('');
    setError('');

    try {
      await apiFetch(`/staff/experiments/${selectedExperiment}`, {
        method: 'DELETE',
        token,
      });
      setMessage('Experiment deleted successfully.');
      setSelectedExperiment(null);
      setForm(EMPTY_FORM);
      await loadStaffData();
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setSaving(false);
    }
  };

  const openStudentDetail = async (studentId) => {
    try {
      const detail = await apiFetch(`/staff/students/${studentId}`, { token });
      setStudentDetail(detail);
    } catch (requestError) {
      setError(requestError.message);
    }
  };

  return (
    <div className="min-h-screen app-shell px-5 py-5 md:px-8 md:py-8">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="hero-orb hero-orb-c"></div>
        <div className="hero-orb hero-orb-d"></div>
        <div className="grid-overlay"></div>
      </div>

      <div className="relative z-10 max-w-7xl mx-auto space-y-6">
        <TopBar user={user} onLogout={onLogout} title="Staff Workspace" subtitle="Student records and experiment management." />

        <div className="grid md:grid-cols-4 gap-4">
          <StatCard label="Students" value={dashboard?.summary.total_students ?? 0} accent="text-cyan-600" />
          <StatCard label="Experiments" value={dashboard?.summary.total_experiments ?? 0} accent="text-emerald-600" />
          <StatCard label="Sessions" value={dashboard?.summary.total_sessions ?? 0} accent="text-amber-600" />
          <StatCard label="Avg Score" value={dashboard?.summary.average_score ?? 0} accent="text-rose-600" />
        </div>

        {error ? <div className="glass-panel p-4 text-sm text-rose-600">{error}</div> : null}
        {message ? <div className="glass-panel p-4 text-sm text-emerald-600">{message}</div> : null}

        <div className="grid xl:grid-cols-[1.15fr_0.85fr] gap-6">
          <section className="space-y-6">
            <div className="glass-panel p-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="eyebrow">Student Performance</p>
                  <h2 className="text-2xl font-semibold text-slate-900 mt-2">Compare outcomes across your class</h2>
                </div>
                <span className="text-xs uppercase tracking-[0.18em] text-slate-500">
                  Click a row for detailed history
                </span>
              </div>
              <div className="mt-5 overflow-hidden rounded-[24px] border border-slate-200">
                <div className="grid grid-cols-[1.35fr_1.2fr_0.8fr_0.9fr_0.9fr] bg-slate-50 px-5 py-4 text-xs uppercase tracking-[0.18em] text-slate-500">
                  <span>Student</span>
                  <span>Email</span>
                  <span>Sessions</span>
                  <span>Evaluations</span>
                  <span>Avg Score</span>
                </div>
                <div className="divide-y divide-slate-200">
                  {(dashboard?.students || []).map((student) => (
                    <button
                      key={student.id}
                      type="button"
                      className="grid grid-cols-[1.35fr_1.2fr_0.8fr_0.9fr_0.9fr] px-5 py-4 text-sm text-slate-700 w-full text-left hover:bg-slate-50 transition-colors"
                      onClick={() => openStudentDetail(student.id)}
                    >
                      <div>
                        <p className="text-slate-900">{student.full_name}</p>
                        <p className="text-xs text-slate-500 mt-1">{student.role_id || 'No ID assigned'}</p>
                      </div>
                      <span>{student.email}</span>
                      <span>{student.session_count}</span>
                      <span>{student.evaluation_count}</span>
                      <span>{student.average_score}</span>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="glass-panel p-6">
              <p className="eyebrow">Recent Evaluations</p>
              <div className="mt-4 space-y-3">
                {(dashboard?.recent_evaluations || []).map((item, index) => (
                  <div key={`${item.student_name}-${index}`} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-slate-900">{item.student_name}</p>
                      <span className="text-sm text-amber-600">{item.score ?? 'Pending'}</span>
                    </div>
                    <p className="text-sm text-slate-600 mt-2">{item.experiment_title}</p>
                  </div>
                ))}
              </div>
            </div>

            {studentDetail ? (
              <div className="glass-panel p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="eyebrow">Student Detail</p>
                    <h3 className="text-2xl font-semibold text-slate-900 mt-2">{studentDetail.student.full_name}</h3>
                    <p className="text-slate-600 mt-2">{studentDetail.student.email}</p>
                  </div>
                  <button className="tab-chip" onClick={() => setStudentDetail(null)}>
                    Close
                  </button>
                </div>
                <div className="grid md:grid-cols-3 gap-4 mt-5">
                  <div className="metric-tile">
                    <span className="metric-tile-label">Sessions</span>
                    <span className="metric-tile-value">{studentDetail.summary.session_count}</span>
                  </div>
                  <div className="metric-tile">
                    <span className="metric-tile-label">Evaluations</span>
                    <span className="metric-tile-value">{studentDetail.summary.evaluation_count}</span>
                  </div>
                  <div className="metric-tile">
                    <span className="metric-tile-label">Avg Score</span>
                    <span className="metric-tile-value">{studentDetail.summary.average_score}</span>
                  </div>
                </div>
                <div className="mt-5 grid lg:grid-cols-2 gap-4">
                  <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-4">
                    <p className="text-sm uppercase tracking-[0.18em] text-slate-500">Recent Sessions</p>
                    <div className="mt-3 space-y-3">
                      {studentDetail.recent_sessions.map((session) => (
                        <div key={session.session_id} className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                          <p className="text-slate-900">{session.experiment}</p>
                          <p className="text-sm text-slate-600 mt-1">{session.mode} | {session.message_count} messages</p>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="rounded-[24px] border border-slate-200 bg-slate-50 p-4">
                    <p className="text-sm uppercase tracking-[0.18em] text-slate-500">Evaluation Feedback</p>
                    <div className="mt-3 space-y-3">
                      {studentDetail.evaluations.map((evaluation, index) => (
                        <div key={`${evaluation.experiment}-${index}`} className="rounded-2xl border border-slate-200 bg-white px-4 py-3">
                          <div className="flex items-center justify-between gap-3">
                            <p className="text-slate-900">{evaluation.experiment}</p>
                            <span className="text-sm text-amber-600">{evaluation.score}</span>
                          </div>
                          <p className="text-sm text-slate-600 mt-2 line-clamp-4">{evaluation.feedback}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            ) : null}
          </section>

          <aside className="space-y-6">
            <div className="glass-panel p-6">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="eyebrow">Experiment Manager</p>
                  <h2 className="text-2xl font-semibold text-slate-900 mt-2">
                    {selectedExperiment ? 'Edit existing experiment' : 'Create a new experiment'}
                  </h2>
                </div>
                <button
                  className="tab-chip"
                  onClick={() => {
                    setSelectedExperiment(null);
                    setForm(EMPTY_FORM);
                    setMessage('');
                    setError('');
                  }}
                >
                  New
                </button>
              </div>

              <div className="mt-4">
                <label className="field-label">Select Published Experiment</label>
                <select
                  value={selectedExperiment || ''}
                  onChange={(event) => selectExperiment(event.target.value)}
                  className="glass-input w-full px-4 py-3"
                >
                    <option value="">Create new experiment</option>
                    {experiments.map((experiment) => (
                    <option key={experiment.slug} value={experiment.slug}>
                      {experiment.title}
                    </option>
                  ))}
                </select>
              </div>

              <div className="mt-5 space-y-4">
                <input
                  className="glass-input w-full px-4 py-3"
                  placeholder="Slug: exp_machine_learning"
                  value={form.slug}
                  onChange={(event) => setForm({ ...form, slug: event.target.value })}
                  disabled={Boolean(selectedExperiment)}
                />
                <input className="glass-input w-full px-4 py-3" placeholder="Title" value={form.title} onChange={(event) => setForm({ ...form, title: event.target.value })} />
                <textarea className="glass-input w-full px-4 py-3 min-h-[100px]" placeholder="Objective" value={form.objective} onChange={(event) => setForm({ ...form, objective: event.target.value })} />
                <textarea className="glass-input w-full px-4 py-3 min-h-[120px]" placeholder="One step per line" value={form.steps} onChange={(event) => setForm({ ...form, steps: event.target.value })} />

                <div className="flex gap-3">
                  <button className="premium-button flex-1 py-3 uppercase tracking-[0.18em] text-xs" onClick={selectedExperiment ? handleUpdate : handleCreate} disabled={saving}>
                    {saving ? 'Saving...' : selectedExperiment ? 'Save Changes' : 'Create Experiment'}
                  </button>
                  {selectedExperiment ? (
                    <button className="danger-button px-5 py-3 uppercase tracking-[0.18em] text-xs" onClick={handleDelete} disabled={saving}>
                      Delete
                    </button>
                  ) : null}
                </div>
              </div>
            </div>

            <div className="glass-panel p-6">
              <p className="eyebrow">Experiment Usage</p>
              <div className="mt-4 space-y-3 max-h-[420px] overflow-y-auto pr-1">
                {(dashboard?.experiments || []).map((experiment) => (
                  <button
                    key={experiment.slug}
                    type="button"
                    className={`w-full rounded-2xl border px-4 py-4 text-left transition-colors ${
                      selectedExperiment === experiment.slug ? 'border-cyan-300 bg-cyan-50' : 'border-slate-200 bg-slate-50 hover:bg-white'
                    }`}
                    onClick={() => selectExperiment(experiment.slug)}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-slate-900">{experiment.title}</p>
                      <span className="text-xs uppercase tracking-[0.18em] text-slate-500">{experiment.session_count} sessions</span>
                    </div>
                    <p className="text-sm text-slate-600 mt-2">
                      {experiment.evaluation_count} evaluations | Avg score {experiment.average_score}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default StaffPortal;
