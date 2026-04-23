// ── Player2 connection logic ──────────────────────────────
var p2PollInterval = null;
function p2SetStatus(state, text) {
    document.getElementById("player2-status-icon").className = state;
    document.getElementById("player2-status-text").textContent = text;
}
function p2SetInfo(text) { document.getElementById("player2-info-text").textContent = text; }
function p2RefreshStatus() {
    p2SetStatus("checking", "Checking...");
    $.ajax({ url: "/player2/status", type: "GET",
        success: function(data) {
            if (data.connected) {
                p2SetStatus("connected", "Connected ✓");
                document.getElementById("player2-detect-btn").style.display  = "none";
                document.getElementById("player2-browser-btn").style.display = "none";
                document.getElementById("player2-disconnect-btn").style.display = "block";
                p2SetInfo("Your NPCs are powered by Player2.");
            } else {
                p2SetStatus("disconnected", "Not connected");
                document.getElementById("player2-detect-btn").style.display  = "block";
                document.getElementById("player2-browser-btn").style.display = "block";
                document.getElementById("player2-disconnect-btn").style.display = "none";
                p2SetInfo(data.app_running ? "Player2 app detected! Click 'Connect via Player2 App'." : "Player2 app not running. Use browser login.");
            }
        },
        error: function() { p2SetStatus("disconnected", "Could not check status"); }
    });
}
document.getElementById("player2-detect-btn").onclick = function() {
    var btn = this; btn.disabled = true; p2SetInfo("Connecting via app...");
    $.ajax({ url: "/player2/connect-app", type: "POST",
        success: function(data) { btn.disabled = false; if (data.success) p2RefreshStatus(); else p2SetInfo("App not available. Try browser login."); },
        error: function() { btn.disabled = false; p2SetInfo("App not found. Try browser login."); }
    });
};
document.getElementById("player2-browser-btn").onclick = function() {
    var btn = this; btn.disabled = true;
    $.ajax({ url: "/player2/connect-device", type: "POST",
        success: function(data) {
            btn.disabled = false;
            if (!data.success) { p2SetInfo("Error: " + data.error); return; }
            window.open(data.verify_url, "_blank");
            document.getElementById("player2-verify-link").href = data.verify_url;
            document.getElementById("player2-verify-link").textContent = data.verify_url;
            document.getElementById("player2-device-approved").style.display   = "none";
            document.getElementById("player2-polling-indicator").style.display = "flex";
            document.getElementById("player2-device-modal").style.display      = "flex";
            var expiresAt = Date.now() + (data.expires_in * 1000);
            p2PollInterval = setInterval(function() {
                if (Date.now() > expiresAt) {
                    clearInterval(p2PollInterval);
                    document.getElementById("player2-device-modal").style.display = "none";
                    p2SetInfo("Login timed out. Please try again.");
                    return;
                }
                $.ajax({ url: "/player2/poll-device", type: "POST",
                    success: function(pd) {
                        if (pd.approved) {
                            clearInterval(p2PollInterval);
                            document.getElementById("player2-polling-indicator").style.display = "none";
                            document.getElementById("player2-device-approved").style.display  = "block";
                            setTimeout(function() { document.getElementById("player2-device-modal").style.display = "none"; p2RefreshStatus(); }, 1500);
                        }
                    }
                });
            }, 5000);
        },
        error: function() { btn.disabled = false; p2SetInfo("Failed to start browser login."); }
    });
};
document.getElementById("player2-cancel-device-btn").onclick = function() {
    if (p2PollInterval) clearInterval(p2PollInterval);
    document.getElementById("player2-device-modal").style.display = "none";
};
document.getElementById("player2-disconnect-btn").onclick = function() {
    if (!confirm("Disconnect from Player2?")) return;
    $.ajax({ url: "/player2/disconnect", type: "POST", success: function() { p2RefreshStatus(); } });
};
p2RefreshStatus();