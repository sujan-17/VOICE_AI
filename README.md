# Voice Lab Assistant

Voice Lab Assistant is a full-stack AI learning platform for guided programming labs, viva evaluation, voice interaction, and performance tracking.

## Stack

- Backend: FastAPI, SQLAlchemy, JWT auth
- Frontend: React, React Router, Tailwind CSS
- AI: Gemini
- Voice: Faster-Whisper for STT and Edge TTS for TTS
- Database: SQLite or PostgreSQL through `DATABASE_URL`

## Features

- Student and staff authentication
- Google login for students
- Experiment-aware assistant mode
- Evaluator mode with AI-generated viva questions
- Text and voice interaction
- Audio playback of AI responses
- Student history, scores, and latency metrics
- Staff dashboard and experiment management

## Setup

### Backend

```bash
cd backend
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm start
```

## Environment

Project root `.env`:

```env
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.5-flash
DATABASE_URL=sqlite:///./voice_lab.db
JWT_SECRET=your_long_random_secret
GOOGLE_CLIENT_ID=your_google_client_id
```

Frontend `frontend/.env`:

```env
REACT_APP_GOOGLE_CLIENT_ID=your_google_client_id
```

## Main Routes

- `POST /auth/login`
- `POST /auth/register`
- `POST /auth/google`
- `GET /auth/me`
- `GET /experiments`
- `GET /student/dashboard`
- `GET /student/history`
- `POST /process-text`
- `POST /process-voice`
- `POST /generate-audio`
- `GET /staff/dashboard`
- `POST /staff/experiments`
- `PUT /staff/experiments/{slug}`
- `DELETE /staff/experiments/{slug}`

## Notes

- Tables are created automatically on backend startup.
- Experiments are seeded from the `experiments/` folder.
- The evaluator now generates its own five viva questions and scores answers without predefined rubric questions.
