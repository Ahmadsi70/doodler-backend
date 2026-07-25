"""Start the backend server."""
import uvicorn
from backend.main import app
print("Starting Story Studio API with OpenAI...")
uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
