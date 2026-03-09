import edge_tts
import asyncio

class TTSService:
    def __init__(self):
        # You can change the voice to "en-GB-SoniaNeural" for a different vibe
        self.voice = "en-US-ChristopherNeural" 

    async def text_to_speech(self, text, output_path):
        """Saves the AI response as an MP3 file."""
        communicate = edge_tts.Communicate(text, self.voice)
        await communicate.save(output_path)
        return output_path