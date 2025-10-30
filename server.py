from waitress import serve
from app import app
import os

if __name__ == "__main__":
    # Bind to the port provided by the platform (e.g., Render sets $PORT)
    port = int(os.environ.get("PORT") or os.environ.get("RENDER_INTERNAL_PORT", 5000))
    serve(app, host="0.0.0.0", port=port)
