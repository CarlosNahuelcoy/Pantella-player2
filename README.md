# Player2 Addon for Pantella

Adds [Player2](https://player2.game) as a native inference engine in [Pantella](https://github.com/Pathos14489/Pantella), powering your Skyrim NPCs with AI conversations through Player2's API.

## Features

- Connect via the **Player2 desktop app** (one click)
- Connect via **browser login** (no app required)
- Automatic health pinging as required by Player2
- Player2 **STT (Speech-to-Text)** support included
- No API key management — everything is handled automatically

## Requirements

- [Pantella](https://github.com/Pathos14489/Pantella) installed and working
- A [Player2 account](https://player2.game) (free to create)
- The [Player2 desktop app](https://player2.game/download) (optional but recommended for easiest setup)

## Installation

1. Download the latest release from [here](https://github.com/CarlosNahuelcoy/Pantella-player2/releases/) and extract the `player2_addon` folder inside your Pantella repository's `addons/` directory:
   ```
   repositories\Pathos14489_Pantella_dev\addons\player2_addon\
   ```

2. In your `config.json`, set the inference engine to Player2:
   ```json
   "LanguageModel": {
       "inference_engine": "player2_api"
   }
   ```

3. Open the Pantella web configurator (http://localhost:8021 while Pantella is running), go to **Inference Engine Settings** → **player2_api** and connect your Player2 account using one of the two options:
   - **Connect via Player2 App** — if you have the desktop app running, one click and you're done
   - **Connect via Browser** — opens a login page, approve it and you're connected

4. Enjoy your AI-powered NPCs!

## Optional: Enable Player2 STT

If you want to use Player2 for speech recognition as well, update your `config.json`:
```json
"SpeechToText": {
    "stt_enabled": true,
    "stt_engine": "player2_stt"
}
```

## Notes

- Your Player2 API key is stored locally and never exposed in the UI
- The addon automatically sends health pings to Player2 every 55 seconds as required by their API
- If your key expires, simply reconnect through the web configurator

## Support

For help, reach out in the **[Pantella Discord](https://discord.gg/pantella)**.

## Credits

- **Pantella** by [Pathos14489](https://github.com/Pathos14489)
- **Player2 integration** by [Gerik Uylerk](https://github.com/CarlosNahuelcoy)
