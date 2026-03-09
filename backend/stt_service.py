from faster_whisper import WhisperModel
import os

# Using 'tiny.en' for maximum speed on localhost
# 'base.en' is slightly more accurate but slower
MODEL_SIZE = "tiny.en"

class STTService:
    def __init__(self):
        # device="cpu" is standard. If you have an NVIDIA GPU, change to "cuda"
        # compute_type="int8" makes it run fast on most CPUs
        self.model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")

    def transcribe(self, audio_path):
        """
        Transcribes audio from file path to text.
        Returns: (text, audio_duration)
        """
        segments, info = self.model.transcribe(
            audio_path,
            beam_size=1,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        
        # Merge segments into one string
        full_text = " ".join([segment.text for segment in segments])
        
        return full_text.strip(), info.duration
