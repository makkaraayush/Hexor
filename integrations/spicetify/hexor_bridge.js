// hexor_bridge.js - Hexor desktop Spotify integration bridge
// Copy this file to your Spicetify Extensions directory:
// Windows: %APPDATA%\spicetify\Extensions\hexor_bridge.js
// Linux/macOS: ~/.config/spicetify/Extensions/hexor_bridge.js
// Then run:
//   spicetify config extensions hexor_bridge.js
//   spicetify apply

(function HexorBridge() {
    function init() {
        if (!window.Spicetify || !Spicetify.Player || !Spicetify.Player.playUri) {
            setTimeout(init, 200);
            return;
        }

        console.log("[HexorBridge] Initialized inside Spotify.");

        let ws = null;
        let reconnectTimer = null;

        function connect() {
            try {
                ws = new WebSocket("ws://127.0.0.1:8000/api/spotify/bridge");

                ws.onopen = () => {
                    console.log("[HexorBridge] Connected to Hexor backend WebSocket.");
                    sendStatus();
                };

                ws.onmessage = (event) => {
                    try {
                        const msg = JSON.parse(event.data);
                        console.log("[HexorBridge] Received command:", msg);
                        if (msg.action === "play_uri" && msg.uri) {
                            Spicetify.Player.playUri(msg.uri);
                        } else if (msg.action === "play") {
                            if (!Spicetify.Player.isPlaying()) Spicetify.Player.play();
                        } else if (msg.action === "pause") {
                            if (Spicetify.Player.isPlaying()) Spicetify.Player.pause();
                        } else if (msg.action === "toggle") {
                            Spicetify.Player.togglePlay();
                        } else if (msg.action === "next") {
                            Spicetify.Player.next();
                        } else if (msg.action === "previous") {
                            Spicetify.Player.previous();
                        }
                    } catch (err) {
                        console.error("[HexorBridge] Message parse error:", err);
                    }
                };

                ws.onclose = () => {
                    if (!reconnectTimer) {
                        reconnectTimer = setTimeout(() => {
                            reconnectTimer = null;
                            connect();
                        }, 2000);
                    }
                };

                ws.onerror = () => {
                    try { ws.close(); } catch(e) {}
                };
            } catch (e) {
                if (!reconnectTimer) {
                    reconnectTimer = setTimeout(() => {
                        reconnectTimer = null;
                        connect();
                    }, 2000);
                }
            }
        }

        function sendStatus() {
            if (ws && ws.readyState === WebSocket.OPEN && Spicetify.Player) {
                const data = Spicetify.Player.data;
                const isPlaying = Spicetify.Player.isPlaying ? Spicetify.Player.isPlaying() : false;
                const item = data && data.item;
                const metadata = item ? (item.metadata || {}) : {};
                ws.send(JSON.stringify({
                    type: "status",
                    is_playing: isPlaying,
                    title: metadata.title || "",
                    artist: metadata.artist_name || "",
                    uri: item ? item.uri : ""
                }));
            }
        }

        Spicetify.Player.addEventListener("songchange", () => {
            setTimeout(sendStatus, 300);
        });

        Spicetify.Player.addEventListener("onplaypause", () => {
            setTimeout(sendStatus, 150);
        });

        connect();
    }

    init();
})();

