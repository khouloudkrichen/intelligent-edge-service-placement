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
from voice_loop  import voice_loop

if __name__ == "__main__":
    threading.Thread(target=voice_loop, daemon=True).start()
    print(f"\n🌐 Dashboard : http://localhost:{SERVER_PORT}")
    uvicorn.run(app, host="0.0.0.0", port=SERVER_PORT, log_level="warning")