let player2_api_inferenceSettings = {{inference_engines.inference_engines["player2_api"]|tojson}};
let player2_api_tabContent = document.createElement("div");
player2_api_tabContent.id = "inference_player2_api_settings";
player2_api_tabContent.className = "tab_content";
let player2_api_header = document.createElement("h3");
player2_api_header.textContent = `{{inference_engine}} - Settings`;
player2_api_tabContent.appendChild(player2_api_header);
player2_api_tabContent.appendChild(document.createElement("br"));
let player2_api_description = document.createElement("p");
player2_api_description.textContent = player2_api_inferenceSettings.description || "No description available for this inference engine.";
player2_api_tabContent.appendChild(player2_api_description);
player2_api_tabContent.appendChild(document.createElement("br"));

let p2panel = document.createElement("div");
p2panel.style.cssText = "background:#5a5a5a; border-radius:6px; padding:16px; margin-top:8px;";
p2panel.innerHTML = `
    <div style="display:flex; align-items:center; gap:8px; margin-bottom:12px;">
        <span id="p2ie-status-icon" style="font-size:1.3em; color:#888;">⬤</span>
        <span id="p2ie-status-text" style="color:#ddd;">Checking...</span>
    </div>
    <p style="color:#bbb; margin-bottom:14px;">
        No extra configuration needed. Just download the Player2 app and connect, or use the browser login. Everything else is handled automatically.
    </p>
    <button id="p2ie-detect-btn" style="background:#6f6f6f; color:white; border:none; padding:10px 16px; cursor:pointer; border-radius:4px; display:block; width:100%; margin-bottom:8px; text-align:left; font-size:0.95em;">🎮 Connect via Player2 App</button>
    <button id="p2ie-browser-btn" style="background:#6f6f6f; color:white; border:none; padding:10px 16px; cursor:pointer; border-radius:4px; display:block; width:100%; margin-bottom:8px; text-align:left; font-size:0.95em;">🌐 Connect via Browser</button>
    <button id="p2ie-disconnect-btn" style="display:none; background:#7a3030; color:white; border:none; padding:10px 16px; cursor:pointer; border-radius:4px; width:100%; text-align:left; font-size:0.95em;">✕ Disconnect</button>
    <p id="p2ie-info-text" style="margin-top:10px; color:#aaa; font-size:0.9em;"></p>
`;
player2_api_tabContent.appendChild(p2panel);
setTimeout(function() {
    function p2ieRefresh() {
        $.ajax({ url: "/player2/status", type: "GET", success: function(data) {
            var icon = document.getElementById("p2ie-status-icon");
            var txt  = document.getElementById("p2ie-status-text");
            if (data.connected) {
                icon.style.color = "#4CAF50"; icon.style.textShadow = "0 0 8px #4CAF50";
                txt.textContent = "Connected ✓";
                document.getElementById("p2ie-detect-btn").style.display     = "none";
                document.getElementById("p2ie-browser-btn").style.display    = "none";
                document.getElementById("p2ie-disconnect-btn").style.display = "block";
                document.getElementById("p2ie-info-text").textContent = "Your NPCs are powered by Player2.";
            } else {
                icon.style.color = "#f44336"; icon.style.textShadow = "";
                txt.textContent = "Not connected";
                document.getElementById("p2ie-detect-btn").style.display     = "block";
                document.getElementById("p2ie-browser-btn").style.display    = "block";
                document.getElementById("p2ie-disconnect-btn").style.display = "none";
                document.getElementById("p2ie-info-text").textContent = data.app_running ? "Player2 app detected!" : "Player2 app not running. Use browser login.";
            }
        }});
    }
    document.getElementById("p2ie-detect-btn").onclick = function() {
        this.disabled = true;
        $.ajax({ url: "/player2/connect-app", type: "POST",
            success: function(d) { document.getElementById("p2ie-detect-btn").disabled = false; if (d.success) p2ieRefresh(); else document.getElementById("p2ie-info-text").textContent = "App not found. Try browser login."; },
            error:   function()  { document.getElementById("p2ie-detect-btn").disabled = false; document.getElementById("p2ie-info-text").textContent = "App not found. Try browser login."; }
        });
    };
    document.getElementById("p2ie-browser-btn").onclick = function() {
        this.disabled = true;
        $.ajax({ url: "/player2/connect-device", type: "POST",
            success: function(data) {
                document.getElementById("p2ie-browser-btn").disabled = false;
                if (!data.success) { document.getElementById("p2ie-info-text").textContent = "Error: " + data.error; return; }
                window.open(data.verify_url, "_blank");
                document.getElementById("p2ie-info-text").textContent = "Browser opened. Waiting for approval...";
                var expiresAt = Date.now() + (data.expires_in * 1000);
                var poll = setInterval(function() {
                    if (Date.now() > expiresAt) { clearInterval(poll); document.getElementById("p2ie-info-text").textContent = "Timed out. Try again."; return; }
                    $.ajax({ url: "/player2/poll-device", type: "POST", success: function(pd) {
                        if (pd.approved) { clearInterval(poll); p2ieRefresh(); }
                    }});
                }, 5000);
            },
            error: function() { document.getElementById("p2ie-browser-btn").disabled = false; document.getElementById("p2ie-info-text").textContent = "Failed to start browser login."; }
        });
    };
    document.getElementById("p2ie-disconnect-btn").onclick = function() {
        if (!confirm("Disconnect from Player2?")) return;
        $.ajax({ url: "/player2/disconnect", type: "POST", success: p2ieRefresh });
    };
    p2ieRefresh();
}, 0);