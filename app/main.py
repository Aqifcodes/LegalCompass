"""
LegalCompass — Flask Application Entry Point
"""
import os
import sys
from pathlib import Path

# Ensure project root is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from app.routes.api import api_bp
from app.routes.translate import translate_bp


def create_app():
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )
    app.config["SECRET_KEY"] = os.getenv("FLASK_SECRET_KEY", "legalcompass-dev-key-change-in-prod")
    app.config["JSON_SORT_KEYS"] = False
    app.config["JSON_AS_ASCII"] = False  # prevents â€" corruption of Unicode chars

    CORS(app, resources={r"/api/*": {"origins": "*"}})
    app.register_blueprint(api_bp)
    app.register_blueprint(translate_bp)

    return app


if __name__ == "__main__":
    app = create_app()
    port = int(os.getenv("FLASK_PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "true").lower() == "true"
    print(f"\n🧭 LegalCompass running at http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=debug)