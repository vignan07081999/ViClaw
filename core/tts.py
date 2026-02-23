import os
import time
import logging
import threading

# Directory to store generated TTS audio files
TTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tts")
os.makedirs(TTS_DIR, exist_ok=True)

class TTSManager:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.engine = None
        self._init_engine()

    @classmethod
    def instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def _init_engine(self):
        try:
            import pyttsx3
            self.engine = pyttsx3.init()
            # Try to select an English voice
            voices = self.engine.getProperty('voices')
            for voice in voices:
                if 'EN-US' in voice.id.upper() or 'ENGLISH' in voice.name.upper():
                    self.engine.setProperty('voice', voice.id)
                    break
            self.engine.setProperty('rate', 165) # normal speaking rate
        except BaseException as e:
            logging.error(f"Failed to initialize pyttsx3: {e}")
            self.engine = None

    def generate_audio(self, text: str) -> str:
        """
        Generates TTS audio for the given text and returns the public URL path.
        Blocks until the file is written.
        """
        if not self.engine:
            return None

        # Clean text (remove markdown, tags, etc.)
        import re
        clean_text = re.sub(r'<[^>]+>', '', text)  # remove pseudo-xml
        clean_text = re.sub(r'\*\*(.*?)\*\*', r'\1', clean_text) # remove bold
        clean_text = re.sub(r'```.*?```', 'code block omitted', clean_text, flags=re.DOTALL) # omit code
        clean_text = clean_text.strip()

        if not clean_text:
            return None

        filename = f"tts_{int(time.time() * 1000)}.mp3"
        filepath = os.path.join(TTS_DIR, filename)

        try:
            with self._lock:
                self.engine.save_to_file(clean_text, filepath)
                self.engine.runAndWait()
            
            # Ensure the file was actually created
            if os.path.exists(filepath):
                return f"/static/tts/{filename}"
            return None
        except Exception as e:
            logging.error(f"TTS generation failed: {e}")
            return None
