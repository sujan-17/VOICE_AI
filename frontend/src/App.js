import React, { useState, useRef, useEffect } from 'react';

function App() {
  const [mode, setMode] = useState('assistant');
  const [isRecording, setIsRecording] = useState(false);
  const [textInput, setTextInput] = useState("");
  const [chatAssistant, setChatAssistant] = useState([]);
  const [chatEvaluator, setChatEvaluator] = useState([]);
  const messagesEndRef = useRef(null);
  const [loading, setLoading] = useState(false);
  const [isAISpeaking, setIsAISpeaking] = useState(false);

  const mediaRecorder = useRef(null);
  const audioChunks = useRef([]);

  const [experiments, setExperiments] = useState([]);
  const [selectedExp, setSelectedExp] = useState("");

  const [sessionIdAssistant, setSessionIdAssistant] = useState("ast_" + Math.random().toString(36).substring(7));
  const [sessionIdEvaluator, setSessionIdEvaluator] = useState("evl_" + Math.random().toString(36).substring(7));

  const handleExperimentChange = (newExp) => {
    setSelectedExp(newExp);
    setChatAssistant([]);
    setChatEvaluator([]);
    setSessionIdAssistant("ast_" + Math.random().toString(36).substring(7));
    setSessionIdEvaluator("evl_" + Math.random().toString(36).substring(7));
  };

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  const [codeSnippet, setCodeSnippet] = useState("");

  const chat = mode === 'assistant' ? chatAssistant : chatEvaluator;
  const sessionId = mode === 'assistant' ? sessionIdAssistant : sessionIdEvaluator;

  // Fetch experiments on load
  useEffect(() => {
    fetch('http://localhost:8000/experiments')
      .then(res => res.json())
      .then(data => {
        if (data.experiments && data.experiments.length > 0) {
          setExperiments(data.experiments);
        }
      })
      .catch(err => console.error("Error fetching experiments:", err));
  }, []);

  // Auto-scroll on new chat messages
  useEffect(() => {
    scrollToBottom();
  }, [chat]);

  // 1. Start Recording Voice
  const startRecording = async () => {
    try {
      // Disable all aggressive browser filters to give Whisper the raw, highest clarity mic data
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: false,
          noiseSuppression: false,
          autoGainControl: false,
          sampleRate: 48000
        }
      });

      // Fallback to MP4 for strict Windows/Realtek compatibility over WebM
      let options = { audioBitsPerSecond: 128000 };
      if (MediaRecorder.isTypeSupported('audio/mp4')) {
        options.mimeType = 'audio/mp4';
      }

      mediaRecorder.current = new MediaRecorder(stream, options);
      audioChunks.current = [];

      mediaRecorder.current.ondataavailable = (e) => {
        if (e.data.size > 0) {
          audioChunks.current.push(e.data);
        }
      };

      mediaRecorder.current.onstop = () => {
        const mimeType = mediaRecorder.current.mimeType || 'audio/webm';
        const audioBlob = new Blob(audioChunks.current, { type: mimeType });

        let ext = 'webm';
        if (mimeType.includes('mp4')) ext = 'mp4';
        else if (mimeType.includes('ogg')) ext = 'ogg';

        sendToBackend(audioBlob, ext);

        // Crucial: Release the hardware lock so consecutive recordings do not fail
        stream.getTracks().forEach(track => track.stop());
        setIsRecording(false);
      };

      mediaRecorder.current.start();
      setIsRecording(true);
    } catch (err) {
      console.error("Microphone access error:", err);
      alert("Microphone access denied or not working. Please check permissions.");
    }
  };

  // 2. Stop Recording
  const stopRecording = () => {
    if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
      mediaRecorder.current.stop(); // This triggers onstop, which will set isRecording(false)
    } else {
      setIsRecording(false);
    }
  };

  const toggleRecording = () => {
    if (isAISpeaking) return;
    if (isRecording) {
      stopRecording();
    } else {
      startRecording();
    }
  };

  const sendTextToBackend = async () => {
    if (!textInput.trim()) return;
    if (!selectedExp) {
      alert("Please select an experiment from the dropdown menu first.");
      return;
    }

    const currentText = textInput;
    setTextInput("");
    setLoading(true);

    const updateChat = mode === 'assistant' ? setChatAssistant : setChatEvaluator;

    // OPTIMISTIC UPDATE
    updateChat((prev) => [
      ...prev,
      { role: 'user', text: currentText }
    ]);

    try {
      const response = await fetch('http://localhost:8000/process-text', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          text: currentText,
          mode: mode,
          session_id: sessionId,
          experiment_id: selectedExp
        })
      });
      const data = await response.json();

      updateChat((prev) => [
        ...prev,
        { role: 'ai', text: data.ai_response }
      ]);

      // Fetch Audio Separately
      const audioResponse = await fetch('http://localhost:8000/generate-audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: data.ai_response, session_id: sessionId })
      });
      const audioData = await audioResponse.json();

      const audio = new Audio(audioData.audio_url);

      audio.onplay = () => setIsAISpeaking(true);
      audio.onended = () => setIsAISpeaking(false);

      audio.play();
    } catch (error) {
      console.error("Error connecting to backend:", error);
      setIsAISpeaking(false);
    } finally {
      setLoading(false);
    }
  };

  // 4. Send Audio to FastAPI
  const sendToBackend = async (audioBlob, ext = 'webm') => {
    if (!selectedExp) {
      alert("Please select an experiment from the dropdown menu first.");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    // Use the native file directly
    formData.append('audio', audioBlob, `recording.${ext}`);
    formData.append('mode', mode);
    formData.append('session_id', sessionId);
    formData.append('experiment_id', selectedExp);

    const updateChat = mode === 'assistant' ? setChatAssistant : setChatEvaluator;

    try {
      const response = await fetch('http://localhost:8000/process-voice', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();

      // Because the user spoke, we didn't know the exact text beforehand.
      // So we append both User Transcription and AI at once here.
      updateChat((prev) => [
        ...prev,
        { role: 'user', text: data.user_said },
        { role: 'ai', text: data.ai_response }
      ]);

      // Fetch Audio Separately
      const audioResponse = await fetch('http://localhost:8000/generate-audio', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text: data.ai_response, session_id: sessionId })
      });
      const audioData = await audioResponse.json();

      // Play AI Voice
      const audio = new Audio(audioData.audio_url);

      audio.onplay = () => setIsAISpeaking(true);
      audio.onended = () => setIsAISpeaking(false);

      audio.play();
    } catch (error) {
      console.error("Error connecting to backend:", error);
      setIsAISpeaking(false);
    } finally {
      setLoading(false);
    }
  };

  return (

    <div className="min-h-screen flex flex-col items-center p-8 relative overflow-hidden">
      {/* Background Decorative Elements */}
      <div className="absolute top-20 left-10 w-96 h-96 bg-blue-600/20 rounded-full blur-[100px] pointer-events-none animate-float"></div>
      <div className="absolute bottom-20 right-10 w-96 h-96 bg-purple-600/20 rounded-full blur-[100px] pointer-events-none animate-float" style={{ animationDelay: '2s' }}></div>

      <header className="text-center mb-8 relative z-10">
        <h1 className="text-5xl font-extrabold bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-400 drop-shadow-lg tracking-tight">AI Lab Assistant</h1>
        <p className="text-slate-400 mt-2 font-light text-lg tracking-wide uppercase">Voice-First Research Environment</p>
      </header>

      {/* Mode Toggle */}
      <div className="glass-panel p-2 flex gap-4 mb-8 relative z-10 rounded-2xl">
        <button
          onClick={() => setMode('assistant')}
          className={`px-8 py-2.5 rounded-xl font-semibold transition-all duration-300 ${mode === 'assistant' ? 'bg-blue-600/80 text-white shadow-[0_0_15px_rgba(37,99,235,0.5)]' : 'text-slate-300 hover:bg-white/5'}`}
        >
          Assistant Mode
        </button>
        <button
          onClick={() => setMode('evaluator')}
          className={`px-8 py-2.5 rounded-xl font-semibold transition-all duration-300 ${mode === 'evaluator' ? 'bg-purple-600/80 text-white shadow-[0_0_15px_rgba(147,51,234,0.5)]' : 'text-slate-300 hover:bg-white/5'}`}
        >
          Evaluator Mode
        </button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 w-full max-w-6xl relative z-10">

        <div className="mb-4 lg:col-span-3">
          <label className="text-xs font-semibold text-slate-400 block mb-2 uppercase tracking-wider">Select Experiment</label>
          <div className="relative">
            <select
              value={selectedExp}
              onChange={(e) => handleExperimentChange(e.target.value)}
              className="appearance-none glass-input w-full p-3.5 text-slate-200 cursor-pointer shadow-lg outline-none"
            >
              <option value="" disabled>-- SELECT AN EXPERIMENT --</option>
              {experiments.map(exp => (
                <option key={exp} value={exp} className="bg-slate-800">
                  {exp.replace('exp_', '').replace(/_/g, ' ').toUpperCase()}
                </option>
              ))}
            </select>
            <div className="pointer-events-none absolute inset-y-0 right-0 flex items-center px-4 text-slate-400">
              ▼
            </div>
          </div>
        </div>

        {/* Chat Interface */}
        <div className="lg:col-span-2 glass-panel p-6 h-[550px] flex flex-col">
          <div className="flex-1 overflow-y-auto space-y-5 mb-4 p-2 custom-scrollbar">
            {chat.map((msg, i) => (
              <div key={i} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] p-4 rounded-2xl shadow-xl transition-all duration-300 ${msg.role === 'user' ? 'bg-gradient-to-br from-blue-600 to-indigo-700 text-white rounded-tr-sm' : 'bg-slate-800/80 border border-slate-700 text-slate-200 rounded-tl-sm'}`}>
                  <p className="text-[10px] font-bold opacity-60 mb-1.5 uppercase tracking-wider">{msg.role === 'user' ? 'You' : 'AI Assistant'}</p>
                  <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.text}</p>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-slate-800/80 border border-slate-700 p-4 rounded-2xl rounded-tl-sm w-fit max-w-[85%]">
                  <p className="flex items-center gap-2 text-blue-400 text-sm font-semibold">
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></span>
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></span>
                    <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></span>
                    Processing...
                  </p>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          <div className="flex justify-center border-t border-white/5 pt-6 pb-3">
            <button
              onClick={toggleRecording}
              disabled={isAISpeaking}
              className={`w-20 h-20 rounded-full flex items-center justify-center transition-all duration-300 shadow-2xl ${isAISpeaking ? 'bg-slate-700 opacity-50 cursor-not-allowed scale-95 text-slate-400' :
                isRecording ? 'bg-red-500 scale-110 shadow-[0_0_30px_rgba(239,68,68,0.6)] animate-pulse-glow text-white' : 'bg-gradient-to-br from-blue-500 to-indigo-600 hover:scale-105 active:scale-95 text-white'
                }`}
            >
              <span className="text-3xl drop-shadow-md">{isAISpeaking ? '🔇' : isRecording ? '⏹️' : '🎙️'}</span>
            </button>
          </div>
          <p className="text-center text-xs font-semibold uppercase tracking-wider text-slate-400">
            {isAISpeaking ? "AI is speaking..." : isRecording ? "Recording... Click to stop" : "Click to speak"}
          </p>

          <div className="flex gap-3 mt-6 bg-slate-800/50 p-2 rounded-xl border border-white/5 shadow-inner">
            <input
              type="text"
              className="flex-1 bg-transparent border-none outline-none text-white text-sm px-4 w-full placeholder-slate-500 font-light"
              placeholder="Or type your message here..."
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  sendTextToBackend();
                }
              }}
            />
            <button
              className="premium-button px-6 py-2.5 text-sm uppercase tracking-wide"
              onClick={sendTextToBackend}
            >
              Send
            </button>
          </div>
        </div>

        <div className="flex flex-col gap-6 h-[550px]">
          {/* Code Workbench */}
          <div className="glass-panel p-6 shadow-xl flex flex-col h-full">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-bold tracking-wide uppercase text-slate-300">Code Workbench</h3>
              <span className="bg-slate-800 text-[10px] px-2 py-1 rounded-full border border-blue-500/30 text-blue-400 font-mono">Input</span>
            </div>
            <textarea
              className="glass-input flex-1 p-3 text-sm font-mono custom-scrollbar resize-none mb-4 min-h-[400px]"
              placeholder="Paste your code here for analysis..."
              value={codeSnippet}
              onChange={(e) => setCodeSnippet(e.target.value)}
            />
            <button
              className="premium-button py-3 text-sm font-bold tracking-wider uppercase flex items-center justify-center gap-2"
              onClick={() => {
                if (codeSnippet.trim()) {
                  setTextInput(`Please analyze this code:\n${codeSnippet}`);
                  // Small delay to allow state to settle before trigger
                  setTimeout(() => sendTextToBackend(), 100);
                  setCodeSnippet("");
                }
              }}
            >
              Analyze Code
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;