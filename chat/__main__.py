"""Run the Story Studio Chat API server."""
from backend.main import app
import uvicorn

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════╗
    ║     Story Studio Chat API v0.3.0        ║
    ║   Chat-centric animation studio          ║
    ║   Agents connected to a unified chat     ║
    ║   Output: Remotion code                  ║
    ╚══════════════════════════════════════════╝
    """)
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
