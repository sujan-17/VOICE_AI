# Voice Lab Assistant

Voice Lab Assistant is a full-stack AI voice application for guided lab experiments.
It supports:
- Speech-to-text input (voice mode)
- Text input (chat mode)
- LLM-generated responses in Assistant and Evaluator modes
- Text-to-speech playback of AI responses
- Session memory and latency/RTF metrics logging

## Tech Stack

- Backend: FastAPI (Python)
- Frontend: React + Tailwind CSS
- AI/Audio services:
- LLM via OpenAI-compatible API client (`openai` package)
- STT via `faster-whisper`
- TTS via `edge-tts`

## Project Structure

```text
voice-lab-assistant/
├── backend/
│   ├── main.py
│   ├── llm_handler.py
│   ├── stt_service.py
│   ├── tts_service.py
│   ├── memory_manager.py
│   ├── metrics.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   └── package.json
└── experiments/
    └── *.json
```

## Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- Git (optional, for version control)

## Environment Variables

Create a `.env` file in the project root (or in `backend/`) with:

```env
NEXUS_API_KEY=your_api_key
NEXUS_BASE_URL=https://your-openai-compatible-endpoint
LLM_MODEL=gpt-4.1-nano
```

Notes:
- `LLM_MODEL` is optional (defaults to `gpt-4.1-nano`).
- `NEXUS_BASE_URL` must be an OpenAI-compatible base URL.

## Backend Setup (FastAPI)

From project root:

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Backend runs at: `http://localhost:8000`

## Frontend Setup (React)

Open a second terminal from project root:

```bash
cd frontend
npm install
npm start
```

Frontend runs at: `http://localhost:3000`

## How to Use

1. Start backend (`python main.py` in `backend/`).
2. Start frontend (`npm start` in `frontend/`).
3. Open `http://localhost:3000`.
4. Select an experiment from the dropdown.
5. Use:
- Mic button for voice input, or
- Text box for typed input.
6. Switch between:
- Assistant Mode (guidance)
- Evaluator Mode (rubric-based questioning)

## API Endpoints (Backend)

- `GET /experiments` - list available experiment IDs
- `POST /process-voice` - transcribe + generate response
- `POST /process-text` - text-only response generation
- `POST /generate-audio` - TTS for given text
- `GET /outputs/...` - static audio file serving

## Troubleshooting

- If frontend cannot connect, ensure backend is running on port `8000`.
- If no AI response is generated, verify `.env` values (`NEXUS_API_KEY`, `NEXUS_BASE_URL`).
- If microphone fails, allow browser mic permissions.
- If Whisper/TTS feels slow on first run, initial model/audio setup may take longer.

