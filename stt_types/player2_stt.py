print('Loading player2_stt.py...')
from src.logging import logging
from src.stt_types.base_whisper import base_Transcriber
import src.utils as utils
logging.info('Imported required libraries in player2_stt.py')

imported = False
try:
    import requests
    imported = True
except ImportError:
    logging.warning("Could not import requests in player2_stt.py. Please make sure it is installed.")

stt_slug = "player2_stt"

PLAYER2_BASE_URL = "https://api.player2.game/v1"
PLAYER2_LOCAL_URL = "http://localhost:4315/v1"
PLAYER2_GAME_CLIENT_ID = "019d4550-51c5-7df8-8a3a-bb9e5f0806f7"  # Fixed — do not expose to users


def _load_key(key_path: str) -> str:
    """Load the Player2 API key from the key file."""
    try:
        import os
        if os.path.exists(key_path):
            with open(key_path, "r") as f:
                key = f.readline().strip()
            if key:
                return key
    except Exception as e:
        logging.warning(f"[Player2 STT] Could not read key file: {e}")
    return ""


def _try_local_app_key() -> str:
    """Try to get a fresh key from the local Player2 app."""
    try:
        resp = requests.post(
            f"{PLAYER2_LOCAL_URL}/login/web/{PLAYER2_GAME_CLIENT_ID}",
            timeout=3,
        )
        resp.raise_for_status()
        return resp.json().get("p2Key", "")
    except Exception:
        return ""


class Transcriber(base_Transcriber):
    """Player2 STT — uses the Player2 /stt/audio endpoint to transcribe audio files.
Shares authentication with the Player2 inference engine (same key file).
Inherits mic capture and audio pipeline from base_whisper."""

    def __init__(self, game_interface):
        global stt_slug
        super().__init__(game_interface)
        self.stt_slug = stt_slug

        if not imported:
            logging.error("[Player2 STT] requests library not found.")
            raise ImportError("requests is required for player2_stt.")

        self._api_key = self._resolve_key()
        if not self._api_key:
            logging.error("[Player2 STT] No Player2 API key found. Run the Player2 app or connect via the web configurator first.")
            raise ValueError("[Player2 STT] No API key available.")

        logging.info("[Player2 STT] Ready.")

    def _resolve_key(self) -> str:
        """Try key file first, then local app."""
        key_path = getattr(self.config, "player2_api_key_path", ".\\PLAYER2_SECRET_KEY.txt")
        key = _load_key(key_path)
        if key:
            logging.info("[Player2 STT] Using key from file.")
            return key
        logging.info("[Player2 STT] Key file empty, trying local app...")
        key = _try_local_app_key()
        if key:
            # Save it for next time
            try:
                with open(key_path, "w") as f:
                    f.write(key)
            except Exception:
                pass
            logging.info("[Player2 STT] Got key from local app.")
            return key
        return ""

    @utils.time_it
    def whisper_transcribe(self, audio: str, prompt=None) -> str:
        """
        Transcribe an audio file using Player2's /stt/audio endpoint.
        audio: path to a WAV file written by the base class pipeline.
        Returns the transcript as a string.
        """
        logging.info("[Player2 STT] Transcribing audio...")

        # Map Pantella language code to Player2 BCP-47 format
        language = getattr(self, "language", "en")
        if not language or language in ("default", "auto"):
            language = "en"

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/octet-stream",
        }
        params = {
            "encoding": "wav",
            "sample_rate": "44100",
            "language": language,
        }

        try:
            with open(audio, "rb") as f:
                audio_bytes = f.read()

            resp = requests.post(
                f"{PLAYER2_BASE_URL}/stt/audio",
                headers=headers,
                params=params,
                data=audio_bytes,
                timeout=30,
            )

            if resp.status_code == 401:
                logging.warning("[Player2 STT] Token expired, refreshing...")
                self._api_key = self._resolve_key()
                if not self._api_key:
                    logging.error("[Player2 STT] Could not refresh key.")
                    return ""
                headers["Authorization"] = f"Bearer {self._api_key}"
                resp = requests.post(
                    f"{PLAYER2_BASE_URL}/stt/audio",
                    headers=headers,
                    params=params,
                    data=audio_bytes,
                    timeout=30,
                )

            if resp.status_code == 402:
                logging.error("[Player2 STT] Insufficient joules. Recharge at https://player2.game/profile/ai-power")
                return ""

            resp.raise_for_status()
            data = resp.json()
            transcript = data.get("transcript", "").strip()
            logging.info(f"[Player2 STT] Transcript: {transcript}")
            return transcript

        except Exception as e:
            logging.error(f"[Player2 STT] Transcription failed: {e}")
            return ""