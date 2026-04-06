import React, { useEffect, useMemo, useRef, useState } from 'react';

import { apiFetch } from '../api';
import { StatCard, TopBar } from '../components/SharedUI';

function StudentPortal({ token, user, onLogout }) {
  const [dashboard, setDashboard] = useState(null);
  const [history, setHistory] = useState([]);
  const [experiments, setExperiments] = useState([]);
  const [selectedExp, setSelectedExp] = useState('');
  const [mode, setMode] = useState('assistant');
  const [sessionIdAssistant, setSessionIdAssistant] = useState('');
  const [sessionIdEvaluator, setSessionIdEvaluator] = useState('');
  const [chatAssistant, setChatAssistant] = useState([]);
  const [chatEvaluator, setChatEvaluator] = useState([]);
  const [textInput, setTextInput] = useState('');
  const [codeSnippet, setCodeSnippet] = useState('');
  const [loading, setLoading] = useState(false);
  const [isRecording, setIsRecording] = useState(false);
  const [isAISpeaking, setIsAISpeaking] = useState(false);
  const [error, setError] = useState('');
  const messagesEndRef = useRef(null);
  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);

  const chat = mode === 'assistant' ? chatAssistant : chatEvaluator;
  const sessionId = mode === 'assistant' ? sessionIdAssistant : sessionIdEvaluator;
  const evaluatorPrompt = chatEvaluator.length ? 'Ask Next Question' : 'Start Viva';

  const isEvaluatorControlMessage = (value) => {
    const normalized = value.trim().toLowerCase().replace(/\s+/g, ' ');
    return ['start', 'start viva', 'start evaluation', 'begin', 'next', 'next question', 'continue', 'go on', 'proceed'].includes(normalized);
  };

  useEffect(() => {
    Promise.all([
      apiFetch('/student/dashboard', { token }),
      apiFetch('/student/history', { token }),
      apiFetch('/experiments', { token }),
    ])
      .then(([dashboardData, historyData, experimentsData]) => {
        setDashboard(dashboardData);
        setHistory(historyData);
        setExperiments(experimentsData);
        if (experimentsData.length > 0) {
          setSelectedExp((current) => current || experimentsData[0].slug);
        }
      })
      .catch((requestError) => {
        console.error(requestError);
        setError(requestError.message);
      });
  }, [token]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chat, loading]);

  const refreshStudentData = async () => {
    const [dashboardData, historyData] = await Promise.all([
      apiFetch('/student/dashboard', { token }),
      apiFetch('/student/history', { token }),
    ]);
    setDashboard(dashboardData);
    setHistory(historyData);
  };

  const playAudio = async (text, activeSessionId) => {
    const audioData = await apiFetch('/generate-audio', {
      method: 'POST',
      token,
      body: JSON.stringify({ text, session_id: activeSessionId }),
    });

    const audio = new Audio(audioData.audio_url);
    audio.onplay = () => setIsAISpeaking(true);
    audio.onended = () => setIsAISpeaking(false);
    audio.play().catch(() => setIsAISpeaking(false));
  };

  const pushChat = (activeMode, updater) => {
    if (activeMode === 'assistant') {
      setChatAssistant(updater);
      return;
    }
    setChatEvaluator(updater);
  };

  const updateSessionState = (activeMode, newSessionId) => {
    if (activeMode === 'assistant') {
      setSessionIdAssistant(newSessionId);
      return;
    }
    setSessionIdEvaluator(newSessionId);
  };

  const sendTextToBackend = async (overrideText) => {
    const content = (overrideText ?? textInput).trim();
    if (!content || !selectedExp) {
      return;
    }

    if (!overrideText) {
      setTextInput('');
    }

    setError('');
    setLoading(true);
    const shouldEchoUser = !(mode === 'evaluator' && isEvaluatorControlMessage(content));
    if (shouldEchoUser) {
      pushChat(mode, (previous) => [...previous, { role: 'user', text: content }]);
    }

    try {
      const data = await apiFetch('/process-text', {
        method: 'POST',
        token,
        body: JSON.stringify({
          text: content,
          mode,
          session_id: sessionId || null,
          experiment_id: selectedExp,
        }),
      });

      updateSessionState(mode, data.session_id);
      pushChat(mode, (previous) => [...previous, { role: 'ai', text: data.ai_response }]);
      await playAudio(data.ai_response, data.session_id);
      await refreshStudentData();
    } catch (requestError) {
      console.error(requestError);
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const sendToBackend = async (audioBlob, extension = 'webm') => {
    if (!selectedExp) {
      return;
    }

    setError('');
    setLoading(true);
    const formData = new FormData();
    formData.append('audio', audioBlob, `recording.${extension}`);
    formData.append('mode', mode);
    formData.append('session_id', sessionId || '');
    formData.append('experiment_id', selectedExp);

    try {
      const data = await apiFetch('/process-voice', {
        method: 'POST',
        token,
        body: formData,
      });

      updateSessionState(mode, data.session_id);
      pushChat(mode, (previous) => [
        ...previous,
        { role: 'user', text: data.user_said },
        { role: 'ai', text: data.ai_response },
      ]);
      await playAudio(data.ai_response, data.session_id);
      await refreshStudentData();
    } catch (requestError) {
      console.error(requestError);
      setError(requestError.message);
    } finally {
      setLoading(false);
    }
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 48000,
        },
      });

      const options = MediaRecorder.isTypeSupported('audio/mp4')
        ? { mimeType: 'audio/mp4', audioBitsPerSecond: 128000 }
        : { audioBitsPerSecond: 128000 };

      mediaRecorder.current = new MediaRecorder(stream, options);
      audioChunks.current = [];

      mediaRecorder.current.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.current.push(event.data);
        }
      };

      mediaRecorder.current.onstop = () => {
        const mimeType = mediaRecorder.current.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunks.current, { type: mimeType });
        const extension = mimeType.includes('mp4') ? 'mp4' : 'webm';
        sendToBackend(audioBlob, extension);
        stream.getTracks().forEach((track) => track.stop());
        setIsRecording(false);
      };

      mediaRecorder.current.start();
      setIsRecording(true);
    } catch (requestError) {
      console.error(requestError);
      setError('Microphone access failed. Please check browser permissions.');
    }
  };

  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state !== 'inactive') {
      mediaRecorder.current.stop();
    }
  };

  const selectedExperiment = useMemo(
    () => experiments.find((experiment) => experiment.slug === selectedExp),
    [experiments, selectedExp]
  );

  return (
    <div className="min-h-screen app-shell px-5 py-5 md:px-8 md:py-8">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="hero-orb hero-orb-a"></div>
        <div className="hero-orb hero-orb-b"></div>
        <div className="grid-overlay"></div>
      </div>
      <div className="relative z-10 max-w-7xl mx-auto space-y-6">
        <TopBar user={user} onLogout={onLogout} title="Student Workspace" subtitle="Experiments, chat history, and evaluation results." />

        <div className="grid md:grid-cols-3 gap-4">
          <StatCard label="Sessions" value={dashboard?.summary.total_sessions ?? 0} accent="text-cyan-600" />
          <StatCard label="Evaluations" value={dashboard?.summary.completed_evaluations ?? 0} accent="text-emerald-600" />
          <StatCard label="Average Score" value={dashboard?.summary.average_score ?? 0} accent="text-amber-600" />
        </div>

        <div className="grid xl:grid-cols-[1.55fr_0.95fr] gap-6">
          <section className="space-y-6">
            <div className="glass-panel p-5">
              <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
                <div>
                  <p className="eyebrow">Experiment</p>
                  <h2 className="text-2xl font-semibold text-slate-900 mt-2">
                    {selectedExperiment?.title || 'Choose an experiment'}
                  </h2>
                  <p className="text-slate-600 mt-3 leading-7">
                    {selectedExperiment?.objective || 'Select an experiment to begin.'}
                  </p>
                </div>
                <select
                  value={selectedExp}
                  onChange={(event) => {
                    setSelectedExp(event.target.value);
                    setChatAssistant([]);
                    setChatEvaluator([]);
                    setSessionIdAssistant('');
                    setSessionIdEvaluator('');
                  }}
                  className="glass-input min-w-[240px] px-4 py-3"
                >
                  {experiments.map((experiment) => (
                    <option key={experiment.slug} value={experiment.slug}>
                      {experiment.title}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="glass-panel p-5">
              <div className="flex flex-wrap gap-3 items-center">
                <button onClick={() => setMode('assistant')} className={`tab-chip ${mode === 'assistant' ? 'tab-chip-active-cyan' : ''}`}>
                  Assistant
                </button>
                <button onClick={() => setMode('evaluator')} className={`tab-chip ${mode === 'evaluator' ? 'tab-chip-active-amber' : ''}`}>
                  Evaluator
                </button>
                <div className="ml-auto text-xs uppercase tracking-[0.18em] text-slate-500">
                  {dashboard?.summary.assistant_sessions ?? 0} assistant | {dashboard?.summary.evaluator_sessions ?? 0} evaluator
                </div>
              </div>

              <div className="mt-5 rounded-[28px] border border-slate-200 bg-white overflow-hidden">
                <div className="h-[430px] overflow-y-auto px-5 py-5 space-y-4">
                  {chat.map((message, index) => (
                    <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`chat-bubble ${message.role === 'user' ? 'chat-bubble-user' : 'chat-bubble-ai'}`}>
                        <p className="text-[11px] uppercase tracking-[0.18em] opacity-70 mb-2">
                          {message.role === 'user' ? 'You' : mode === 'assistant' ? 'Assistant' : 'Evaluator'}
                        </p>
                        <p className="whitespace-pre-wrap leading-7">{message.text}</p>
                      </div>
                    </div>
                  ))}
                  {loading ? <div className="text-sm text-slate-500">Generating response...</div> : null}
                  <div ref={messagesEndRef}></div>
                </div>

                <div className="border-t border-slate-200 p-5">
                  <div className="flex flex-col gap-4 lg:flex-row">
                    <input
                      className="glass-input flex-1 px-4 py-3"
                      value={textInput}
                      onChange={(event) => setTextInput(event.target.value)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter') {
                          sendTextToBackend();
                        }
                      }}
                      placeholder={mode === 'assistant' ? 'Type your question or response' : 'Type your answer or use Start Viva / Ask Next Question'}
                    />
                    <button className="premium-button px-6 py-3 uppercase tracking-[0.18em] text-xs" onClick={() => sendTextToBackend()} disabled={loading}>
                      Send
                    </button>
                    {mode === 'evaluator' ? (
                      <button className="tab-chip" onClick={() => sendTextToBackend(chatEvaluator.length ? 'next question' : 'start viva')} disabled={loading}>
                        {evaluatorPrompt}
                      </button>
                    ) : null}
                    <button
                      className={`voice-button ${isRecording ? 'voice-button-recording' : ''}`}
                      onClick={() => (isRecording ? stopRecording() : startRecording())}
                      disabled={loading || isAISpeaking}
                    >
                      {isRecording ? 'Stop' : 'Voice'}
                    </button>
                  </div>
                  <p className="text-xs uppercase tracking-[0.18em] text-slate-500 mt-3">
                    {isAISpeaking ? 'Audio playing' : isRecording ? 'Recording' : 'Ready'}
                  </p>
                  {error ? <p className="text-sm text-rose-600 mt-3">{error}</p> : null}
                </div>
              </div>
            </div>
          </section>

          <aside className="space-y-6">
            <div className="glass-panel p-5">
              <p className="eyebrow">Code Workbench</p>
              <textarea
                className="glass-input w-full min-h-[180px] mt-4 px-4 py-4 font-mono text-sm"
                value={codeSnippet}
                onChange={(event) => setCodeSnippet(event.target.value)}
                placeholder="Paste code for explanation or debugging"
              />
              <button
                className="premium-button w-full py-3 mt-4 uppercase tracking-[0.18em] text-xs"
                onClick={() => {
                  if (!codeSnippet.trim()) return;
                  sendTextToBackend(`Please analyze this code and explain any issues:\n${codeSnippet}`);
                  setCodeSnippet('');
                }}
              >
                Analyze Code
              </button>
            </div>

            <div className="glass-panel p-5">
              <p className="eyebrow">Experiment Progress</p>
              <div className="mt-4 space-y-3 max-h-[250px] overflow-y-auto pr-1">
                {(dashboard?.experiment_progress || []).map((item) => (
                  <div key={item.slug} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-slate-900">{item.title}</p>
                      <span className="text-xs uppercase tracking-[0.18em] text-slate-500">{item.session_count} sessions</span>
                    </div>
                    <p className="text-sm text-slate-600 mt-2">
                      Latest score: {item.latest_score ?? 'Pending'} | Best score: {item.best_score ?? 'Pending'}
                    </p>
                  </div>
                ))}
              </div>
            </div>

            <div className="glass-panel p-5">
              <p className="eyebrow">History</p>
              <div className="mt-4 space-y-4 max-h-[420px] overflow-y-auto pr-1">
                {history.map((item) => (
                  <div key={item.session_id} className="rounded-2xl border border-slate-200 bg-slate-50 px-4 py-4">
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-slate-900">{item.experiment}</p>
                      <span className="text-xs uppercase tracking-[0.18em] text-slate-500">{item.mode}</span>
                    </div>
                    <div className="mt-3 space-y-2">
                      {item.messages.map((message) => (
                        <div key={message.id} className={`history-message ${message.role === 'user' ? 'history-message-user' : 'history-message-ai'}`}>
                          <span className="history-message-role">{message.role === 'user' ? 'You' : 'Assistant'}</span>
                          <p>{message.content}</p>
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
                {!history.length ? <p className="text-sm text-slate-500">No saved sessions yet.</p> : null}
              </div>
            </div>
          </aside>
        </div>
      </div>
    </div>
  );
}

export default StudentPortal;
