import uvicorn
import webbrowser
import threading
import time
from backend.config import config

def open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://{config.HOST}:{config.PORT}")

if __name__ == "__main__":
    print("=" * 60)
    print("HEXOR // JARVIS AUTONOMOUS AGENT SYSTEM")
    print(f"Launching on: http://{config.HOST}:{config.PORT}")
    print("=" * 60)
    
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("backend.main:app", host=config.HOST, port=config.PORT, reload=True)

