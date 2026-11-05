import os
import sys
import uvicorn
import webbrowser
import threading
import time
from backend.config import config

def open_browser():
    time.sleep(1.2)
    webbrowser.open(f"http://{config.HOST}:{config.PORT}")

if __name__ == "__main__":
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleTitleW("HEXOR AI OS")
        except Exception:
            pass

    print("=" * 60)
    print("HEXOR // JARVIS AUTONOMOUS AGENT SYSTEM")
    print(f"Launching on: http://{config.HOST}:{config.PORT}")
    print("=" * 60)
    
    threading.Thread(target=open_browser, daemon=True).start()
    
    dev_mode = os.getenv("HEXOR_DEV", "false").lower() == "true"
    uvicorn.run("backend.main:app", host=config.HOST, port=config.PORT, reload=dev_mode)
