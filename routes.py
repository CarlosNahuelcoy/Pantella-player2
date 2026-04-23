from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
import os
import json
import requests as req

PLAYER2_BASE_URL = "https://api.player2.game/v1"
PLAYER2_LOCAL_URL = "http://localhost:4315/v1"
PLAYER2_GAME_CLIENT_ID = "019d4550-51c5-7df8-8a3a-bb9e5f0806f7"

def main(app: FastAPI, templates: Jinja2Templates, config_loader):

    @app.get("/player2/status")
    def player2_status():
        key_path = os.path.abspath(getattr(config_loader, "player2_api_key_path", ".\\PLAYER2_SECRET_KEY.txt"))
        has_key = False
        if os.path.exists(key_path):
            with open(key_path, "r") as f:
                has_key = bool(f.readline().strip())
        app_running = False
        try:
            r = req.post(f"{PLAYER2_LOCAL_URL}/login/web/{PLAYER2_GAME_CLIENT_ID}", timeout=2)
            app_running = r.status_code == 200
        except Exception:
            pass
        return JSONResponse({"connected": has_key, "app_running": app_running})

    @app.post("/player2/connect-app")
    def player2_connect_app():
        try:
            r = req.post(f"{PLAYER2_LOCAL_URL}/login/web/{PLAYER2_GAME_CLIENT_ID}", timeout=3)
            r.raise_for_status()
            key = r.json().get("p2Key", "")
            if not key:
                return JSONResponse({"success": False, "error": "No key returned by app"}, status_code=400)
            key_path = os.path.abspath(getattr(config_loader, "player2_api_key_path", ".\\PLAYER2_SECRET_KEY.txt"))
            with open(key_path, "w") as f:
                f.write(key)
            return JSONResponse({"success": True})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    @app.post("/player2/connect-device")
    def player2_connect_device():
        try:
            r = req.post(f"{PLAYER2_BASE_URL}/login/device/new", json={"client_id": PLAYER2_GAME_CLIENT_ID}, timeout=15)
            r.raise_for_status()
            data = r.json()
            tmp_path = os.path.abspath(".\\player2_device_flow_tmp.json")
            with open(tmp_path, "w") as f:
                json.dump(data, f)
            return JSONResponse({
                "success": True,
                "verify_url": data["verificationUriComplete"],
                "user_code": data["userCode"],
                "expires_in": data["expiresIn"],
            })
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    @app.post("/player2/poll-device")
    def player2_poll_device():
        tmp_path = os.path.abspath(".\\player2_device_flow_tmp.json")
        if not os.path.exists(tmp_path):
            return JSONResponse({"success": False, "error": "No device flow in progress"}, status_code=400)
        try:
            with open(tmp_path, "r") as f:
                data = json.load(f)
            poll = req.post(
                f"{PLAYER2_BASE_URL}/login/device/token",
                json={"client_id": PLAYER2_GAME_CLIENT_ID, "device_code": data["deviceCode"], "grant_type": "urn:ietf:params:oauth:grant-type:device_code"},
                timeout=10,
            )
            if poll.status_code == 200:
                key = poll.json().get("p2Key", "")
                if key:
                    key_path = os.path.abspath(getattr(config_loader, "player2_api_key_path", ".\\PLAYER2_SECRET_KEY.txt"))
                    with open(key_path, "w") as f:
                        f.write(key)
                    os.remove(tmp_path)
                    return JSONResponse({"success": True, "approved": True})
            return JSONResponse({"success": True, "approved": False})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)

    @app.post("/player2/disconnect")
    def player2_disconnect():
        key_path = os.path.abspath(getattr(config_loader, "player2_api_key_path", ".\\PLAYER2_SECRET_KEY.txt"))
        try:
            with open(key_path, "w") as f:
                f.write("")
            return JSONResponse({"success": True})
        except Exception as e:
            return JSONResponse({"success": False, "error": str(e)}, status_code=400)