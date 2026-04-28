# ═══════════════════════════════════════════════════════
# main.py — Point d'entrée IBN Voice
#
# Lancer :
#   ollama serve          (terminal 1)
#   python main.py        (terminal 2)
#   Ouvrir : http://localhost:8081
# ═══════════════════════════════════════════════════════

import threading
import uvicorn

from config      import SERVER_PORT
from api.server  import app
from data.dataset import preload_dataset
from core.detection import preload_detection_profiles
from voice_loop  import voice_loop

if __name__ == "__main__":
    cache = preload_dataset()
    detection_profiles = preload_detection_profiles()
    print(
        f"\n✅ Dataset preloaded: "
        f"{len(cache['nodes'])} nodes, {len(cache['services'])} services, "
        f"{len(cache['intentions'])} intentions"
    )
    print(f"✅ Detection profiles ready: {len(detection_profiles)} intentions")
    threading.Thread(target=voice_loop, daemon=True).start()
    print(f"\n🌐 Dashboard : http://localhost:{SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level="warning")
