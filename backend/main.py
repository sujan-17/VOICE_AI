import os
import time
import uuid
import shutil
from fastapi import FastAPI, UploadFile, File, Form, Body, HTTPException, BackgroundTasks
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import our custom modules
from stt_service import STTService
from llm_handler import LLMHandler
from tts_service import TTSService
from metrics import PerformanceMetrics

from memory_manager import MemoryManager

memory = MemoryManager()

app = FastAPI()

# 1. Setup CORS (Allows React frontend to talk to this backend)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Initialize Services
stt = STTService()
llm = LLMHandler()
tts = TTSService()
perf = PerformanceMetrics()

# 3. Create folders for audio files
OUTPUT_DIR = "outputs"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Serve the output folder so the frontend can play the audio files
app.mount("/outputs", StaticFiles(directory=OUTPUT_DIR), name="outputs")

@app.get("/experiments")
async def list_experiments():
    # Looks into the 'experiments' folder and returns the titles
    files = [f for f in os.listdir("../experiments") if f.endswith(".json")]
    return {"experiments": [f.replace(".json", "") for f in files]}

@app.post("/process-voice")
async def process_voice(
    audio: UploadFile = File(...), 
    mode: str = Form(...),
    experiment_id: str = Form(...),
    session_id: str = Form(...)
):
    
    """
    Main pipeline: Audio -> Text -> Context -> LLM -> Speech
    """
    output_filename = f"{session_id}_response.mp3"
    output_path = os.path.join(OUTPUT_DIR, output_filename)

    # Read audio into memory
    audio_bytes = await audio.read()

    # Extract dynamic file extension to match the frontend perfectly
    file_ext = audio.filename.split('.')[-1] if audio.filename and '.' in audio.filename else 'webm'

    # DEBUG: Save exactly what the frontend is sending so we can inspect it
    with open(f"debug_upload_{session_id}.{file_ext}", "wb") as f:
        f.write(audio_bytes)
        
    perf.start_timer()

    # --- PHASE 1: STT (Transcription) ---
    stt_start = time.perf_counter()
    
    # Write to standard disk file to bypass Windows tempfile locks, then aggressively clean it up
    tmp_path = os.path.join(OUTPUT_DIR, f"temp_{session_id}.{file_ext}")
    with open(tmp_path, "wb") as w:
        w.write(audio_bytes)
        
    try:
        transcript, audio_duration = stt.transcribe(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
            
    stt_end = time.perf_counter()
    
    stt_latency = stt_end - stt_start
    rtf = perf.calculate_rtf(stt_latency, audio_duration)

    if not transcript.strip():
        # Prevent hallucinating responses to pure silence, but handle gracefully
        print("[WARNING] STT returned an empty string. Returning graceful fallback.")
        ai_text = "I didn't catch that. Could you try speaking again, or type your message?"
        
        # We must generate fallback audio explicitly since we are skipping the LLM
        tts_start = time.perf_counter()
        await tts.text_to_speech(ai_text, output_path)
        tts_end = time.perf_counter()
        
        cache_buster = str(uuid.uuid4())[:8]
        audio_url = f"http://localhost:8000/outputs/{output_filename}?cb={cache_buster}"
        
        return {
            "user_said": "[Silence Detected]",
            "ai_response": ai_text,
            "audio_url": audio_url
        }

    # --- Context Gathering ---
    # 1. Get previous conversation history
    history = memory.get_history(session_id)

    # --- PHASE 2: LLM (Brain) ---
    llm_start = time.perf_counter()
    try:
        ai_text = await llm.get_response(
            transcript, 
            mode=mode, 
            exp_id=experiment_id, 
            history=history
        )
    except Exception as e:
        print(f"LLM Error: {e}")
        raise HTTPException(status_code=500, detail="Error generating AI response")
        
    llm_end = time.perf_counter()
    llm_latency = llm_end - llm_start
    
    total_latency = perf.stop_timer()

    # Save this turn to memory
    memory.add_message(session_id, "user", transcript)
    memory.add_message(session_id, "assistant", ai_text)

    print(f"\n[EVALUATION METRICS] Session {session_id}")
    print(f"  Total Turnaround Latency: {total_latency:.2f}s")
    print(f"  STT Engine Latency: {stt_latency:.2f}s")
    print(f"  LLM Generation Latency: {llm_latency:.2f}s")
    print(f"  STT Real-Time Factor (RTF): {rtf:.2f}")
    
    perf.log_metrics(session_id, "Voice", total_latency, llm_latency, stt_latency, rtf)

    # --- PHASE 3: Return Results ---
    return {
        "user_said": transcript,
        "ai_response": ai_text
    }

class TextRequest(BaseModel):
    text: str
    mode: str
    experiment_id: str
    session_id: str

@app.post("/process-text")
async def process_text(request: TextRequest):
    """Handles purely text-based input instead of audio."""
    perf.start_timer()
    
    # 1. Get memory
    history = memory.get_history(request.session_id)
    
    print(f"=== INCOMING API TEXT REQUEST ===")
    print(f"Experiment ID: '{request.experiment_id}'")
    print(f"Text String: '{request.text}'")

    # 2. Pass to LLM
    llm_start = time.perf_counter()
    try:
        ai_text = await llm.get_response(
            request.text, 
            mode=request.mode, 
            exp_id=request.experiment_id, 
            history=history
        )
    except Exception as e:
        print(f"LLM Error: {e}")
        raise HTTPException(status_code=500, detail="Error generating AI response")
        
    llm_end = time.perf_counter()
    llm_latency = llm_end - llm_start

    # Save to memory
    memory.add_message(request.session_id, "user", request.text)
    memory.add_message(request.session_id, "assistant", ai_text)

    total_latency = perf.stop_timer()
    print(f"\n[EVALUATION METRICS] Text Request {request.session_id}")
    print(f"  Total Turnaround Latency: {total_latency:.2f}s")
    print(f"  LLM Generation Latency: {llm_latency:.2f}s")
    
    perf.log_metrics(request.session_id, "Text", total_latency, llm_latency)

    return {
        "user_said": request.text,
        "ai_response": ai_text
    }

class AudioRequest(BaseModel):
    text: str
    session_id: str

@app.post("/generate-audio")
async def generate_audio(request: AudioRequest):
    output_filename = f"{request.session_id}_response.mp3"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    
    tts_start = time.perf_counter()
    await tts.text_to_speech(request.text, output_path)
    tts_end = time.perf_counter()
    
    cache_buster = str(uuid.uuid4())[:8]
    return {
        "audio_url": f"http://localhost:8000/outputs/{output_filename}?v={cache_buster}"
    }



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)