print("Importing player2_api.py")
from src.logging import logging, time
import src.utils as utils
import src.inference_engines.base_llm as base_LLM
import traceback
import threading
import os
import json
import webbrowser
logging.info("Imported required libraries in player2_api.py")

imported = False
try:
    import requests
    imported = True
    logging.info("Imported requests in player2_api.py")
except Exception as e:
    logging.warn("Failed to load requests, so player2_api cannot be used! Please check that you have installed it correctly.")

inference_engine_name = "player2_api"
inference_engine_title = "Player2"
tokenizer_slug = "tiktoken"

PLAYER2_BASE_URL = "https://api.player2.game/v1"
PLAYER2_LOCAL_URL = "http://localhost:4315/v1"
HEALTH_PING_INTERVAL = 55  # seconds (spec says 60, with margin)
PLAYER2_GAME_CLIENT_ID = "019d4550-51c5-7df8-8a3a-bb9e5f0806f7"  # Fixed — do not expose to users

default_settings = {
    "player2_model": "default",
    "player2_auth_method": "app",  # "app" | "key" | "device"
    "player2_api_key_path": ".\\PLAYER2_SECRET_KEY.txt",
}
settings_description = {
    "player2_model": "The model to use for Player2. Use 'default' to let Player2 choose, or specify a model name.",
    "player2_auth_method": "Authentication method: 'app' (use local Player2 desktop app), 'key' (use API key file), or 'device' (OAuth device flow via browser).",
    "player2_api_key_path": "Path to the file containing your Player2 API key. Only used when auth_method is 'key'.",
}
options = {
    "player2_auth_method": ["app", "key", "device"],
}
settings = {}
loaded = False
description = "Player2 API Inference Engine for Pantella. Connects to Player2 (https://player2.game) using OpenAI-compatible chat completions. Supports authentication via the Player2 desktop app, a direct API key, or OAuth device flow."


# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────

def _login_via_local_app(game_client_id: str):
    """Try to get p2Key from the locally running Player2 desktop app."""
    try:
        resp = requests.post(
            f"{PLAYER2_LOCAL_URL}/login/web/{game_client_id}",
            timeout=3,
        )
        resp.raise_for_status()
        return resp.json().get("p2Key")
    except Exception:
        return None


def _login_device_flow(game_client_id: str):
    """OAuth Device Code Flow — opens browser, polls until approved."""
    try:
        r = requests.post(
            f"{PLAYER2_BASE_URL}/login/device/new",
            json={"client_id": game_client_id},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        device_code = data["deviceCode"]
        expires_in  = data["expiresIn"]
        interval    = data["interval"]
        verify_url  = data["verificationUriComplete"]
        user_code   = data["userCode"]

        logging.info(f"[Player2] Open this URL to authenticate: {verify_url}")
        logging.info(f"[Player2] Manual code if needed: {user_code}")
        print(f"\n[Player2] Open this URL in your browser to connect Player2:\n  {verify_url}\n  (Code: {user_code})\n")
        try:
            webbrowser.open(verify_url)
        except Exception:
            pass

        deadline = time.time() + expires_in
        while time.time() < deadline:
            time.sleep(interval)
            try:
                poll = requests.post(
                    f"{PLAYER2_BASE_URL}/login/device/token",
                    json={
                        "client_id":   game_client_id,
                        "device_code": device_code,
                        "grant_type":  "urn:ietf:params:oauth:grant-type:device_code",
                    },
                    timeout=15,
                )
                if poll.status_code == 200:
                    key = poll.json().get("p2Key")
                    if key:
                        return key
            except Exception:
                pass

        logging.error("[Player2] Device flow authorization expired.")
        return None
    except Exception as e:
        logging.error(f"[Player2] Device flow failed: {e}")
        return None


def _resolve_api_key(config) -> str:
    """
    Resolves the Player2 API key based on auth_method in config.
    Priority: app local → key file → device flow
    The game client ID is fixed internally and not exposed to the user.
    """
    method   = getattr(config, "player2_auth_method", "app")
    key_path = getattr(config, "player2_api_key_path", ".\\PLAYER2_SECRET_KEY.txt")

    # Always try local app first if method allows it
    if method in ("app", "device"):
        key = _login_via_local_app(PLAYER2_GAME_CLIENT_ID)
        if key:
            logging.info("[Player2] Authenticated via local app.")
            return key
        if method == "app":
            logging.warn("[Player2] Local app not found. Falling back to key file.")

    # Try key file
    if os.path.exists(key_path):
        with open(key_path, "r") as f:
            key = f.readline().strip()
        if key:
            logging.info("[Player2] Authenticated via API key file.")
            return key

    # Device flow fallback
    logging.info("[Player2] Starting Device Code Flow...")
    key = _login_device_flow(PLAYER2_GAME_CLIENT_ID)
    if key:
        logging.info("[Player2] Authenticated via Device Flow.")
        return key

    raise ValueError(
        "[Player2] Could not authenticate. Set player2_auth_method and either run the "
        "Player2 desktop app, provide a key in PLAYER2_SECRET_KEY.txt, or use auth_method=device for browser login."
    )


# ─────────────────────────────────────────────
# INFERENCE ENGINE
# ─────────────────────────────────────────────

class LLM(base_LLM.base_LLM):
    """Player2 API Inference Engine for Pantella.
Connects to Player2 (https://player2.game) using OpenAI-compatible chat completions.
Supports three auth modes: local desktop app, direct API key, or OAuth device flow.
Automatically sends health pings every 55 seconds as required by Player2."""

    def __init__(self, conversation_manager, vision_enabled=False):
        global inference_engine_name, tokenizer_slug, loaded, default_settings
        super().__init__(conversation_manager, vision_enabled=vision_enabled)
        self.inference_engine_name = inference_engine_name
        self.tokenizer_slug = tokenizer_slug
        default_settings = self.default_inference_engine_settings
        self.is_local = False

        if not imported:
            logging.error("[Player2] requests library not found. Please install it.")
            input("Press Enter to exit.")
            raise ImportError("requests is required for player2_api.")

        # Resolve authentication
        self.api_key = _resolve_api_key(self.config)

        # Build session with auth header
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })
        self.client = self.session  # required for tiktoken tokenizer

        # Determine model
        model_setting = getattr(self.config, "player2_model", "default")
        self.llm = None if model_setting == "default" else model_setting

        # Check joules balance
        self._check_joules()

        # Start health ping thread
        self._stop_health = threading.Event()
        self._health_thread = threading.Thread(
            target=self._health_loop, daemon=True, name="P2HealthPing"
        )
        self._health_thread.start()

        # Quick connectivity test
        self._test_connection()

        logging.info(f"[Player2] Ready. Model: {self.llm or 'default'}")
        loaded = True

    def _check_joules(self):
        try:
            resp = self.session.get(f"{PLAYER2_BASE_URL}/joules", timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                joules = data.get("joules", "?")
                tier   = data.get("patron_tier", "")
                tier_str = f" | Tier: {tier}" if tier else ""
                logging.info(f"[Player2] Joules available: {joules}{tier_str}")
                if isinstance(joules, int) and joules < 5:
                    logging.warn(
                        f"[Player2] Low joules ({joules}). "
                        "Recharge at https://player2.game/profile/ai-power"
                    )
        except Exception as e:
            logging.warn(f"[Player2] Could not check joules: {e}")

    def _test_connection(self):
        try:
            resp = self.session.get(f"{PLAYER2_BASE_URL}/health", timeout=10)
            if resp.status_code == 200:
                logging.info("[Player2] Health check OK.")
            else:
                logging.warn(f"[Player2] Health check returned {resp.status_code}.")
        except Exception as e:
            logging.warn(f"[Player2] Health check failed: {e}")

    def _health_loop(self):
        while not self._stop_health.wait(HEALTH_PING_INTERVAL):
            try:
                resp = self.session.get(f"{PLAYER2_BASE_URL}/health", timeout=10)
                if resp.status_code == 200:
                    logging.info("[Player2] Health ping OK.")
                else:
                    logging.warn(f"[Player2] Health ping returned {resp.status_code}.")
            except Exception as e:
                logging.warn(f"[Player2] Health ping failed: {e}")

    def __del__(self):
        try:
            self._stop_health.set()
        except Exception:
            pass

    @property
    def default_inference_engine_settings(self):
        return {
            "player2_model":       getattr(self.config, "player2_model", "default"),
            "player2_auth_method": getattr(self.config, "player2_auth_method", "app"),
            "player2_api_key_path": getattr(self.config, "player2_api_key_path", ".\\PLAYER2_SECRET_KEY.txt"),
        }

    def _build_payload(self, messages: list, stream: bool = False) -> dict:
        payload = {
            "messages":    messages,
            "max_tokens":  self.config.max_tokens,
            "temperature": self.temperature,
            "top_p":       self.top_p,
            "stream":      stream,
        }
        if self.llm:
            payload["model"] = self.llm

        # Remove banned samplers
        banned = getattr(self.config, "banned_samplers", [])
        for key in banned:
            payload.pop(key, None)

        return payload

    def _log_request(self, payload: dict):
        if not getattr(self.config, "log_all_api_requests", False):
            return
        try:
            log_dir = self.config.api_log_dir
            os.makedirs(log_dir, exist_ok=True)
            taken = set()
            for f in os.listdir(log_dir):
                if f.endswith(".json") or f.endswith(".log"):
                    taken.add(f.split(".")[0])
            sorted_ids = sorted(taken)
            log_id = str(int(sorted_ids[-1]) + 1) if sorted_ids else "1"
            with open(os.path.join(log_dir, f"{log_id}.json"), "w") as f:
                json.dump(payload, f)
        except Exception as e:
            logging.warn(f"[Player2] Could not write API log: {e}")

    def _handle_response_errors(self, resp):
        if resp.status_code == 401:
            raise ValueError("[Player2] Invalid or expired token. Re-authenticate with Player2.")
        if resp.status_code == 402:
            raise ValueError(
                "[Player2] Insufficient joules. Recharge at https://player2.game/profile/ai-power"
            )
        if resp.status_code == 429:
            raise ValueError("[Player2] Rate limit hit. Retrying...")
        resp.raise_for_status()

    @utils.time_it
    def create(self, messages):
        retries = self.config.retries if hasattr(self.config, "retries") else 3
        completion = None

        while retries > 0 and completion is None:
            try:
                payload = self._build_payload(messages, stream=False)
                self._log_request(payload)

                resp = self.session.post(
                    f"{PLAYER2_BASE_URL}/chat/completions",
                    json=payload,
                    timeout=60,
                )
                self._handle_response_errors(resp)

                data = resp.json()
                completion = data["choices"][0]["message"]["content"]

                if not isinstance(completion, str):
                    raise ValueError("[Player2] Unexpected response format from API.")

                logging.info(f"[Player2] Completion: {completion}")
            except Exception as e:
                logging.warn(f"[Player2] Could not connect to API, retrying in 5 seconds... ({e})")
                tb = traceback.format_exc()
                logging.error(tb)
                if retries == 1:
                    logging.error("[Player2] Could not connect after max retries.")
                    input("Press Enter to continue...")
                    raise e
                time.sleep(5)
                retries -= 1
                continue
            break

        if not isinstance(completion, str):
            raise ValueError("[Player2] Could not get a valid completion from Player2 API.")
        return completion

    @utils.time_it
    def acreate(self, messages, message_prefix="", force_speaker=None):
        retries = self.config.retries if hasattr(self.config, "retries") else 3

        while retries > 0:
            try:
                # Append forced speaker prefill if needed
                if force_speaker is not None and self._prompt_style.get("force_speaker"):
                    force_speaker_string = force_speaker.name + self.config.message_signifier
                    logging.info(f"[Player2] Assistant Prefill (Forced Author): {force_speaker_string}")
                    messages.append({"role": "assistant", "content": force_speaker_string})

                if message_prefix:
                    logging.info(f"[Player2] Assistant Prefill (Message prefix): {message_prefix}")
                    if force_speaker is not None:
                        messages[-1]["content"] += message_prefix
                    else:
                        messages.append({"role": "assistant", "content": message_prefix})

                payload = self._build_payload(messages, stream=True)
                self._log_request(payload)

                with self.session.post(
                    f"{PLAYER2_BASE_URL}/chat/completions",
                    json=payload,
                    stream=True,
                    timeout=60,
                ) as resp:
                    self._handle_response_errors(resp)
                    for line in resp.iter_lines():
                        if not line:
                            continue
                        decoded = line.decode("utf-8")
                        if decoded.startswith("data: "):
                            data_str = decoded[6:]
                            if data_str == "[DONE]":
                                break
                            try:
                                chunk = json.loads(data_str)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta and delta.strip():
                                    logging.info(f"[Player2] Stream chunk: {delta}")
                                    yield delta
                            except Exception:
                                pass
                break  # success — exit retry loop

            except Exception as e:
                logging.warn(f"[Player2] Streaming error, retrying in 5 seconds... ({e})")
                tb = traceback.format_exc()
                logging.error(tb)
                if retries == 1:
                    logging.error("[Player2] Could not stream after max retries.")
                    input("Press Enter to continue...")
                    raise e
                time.sleep(5)
                retries -= 1
                continue