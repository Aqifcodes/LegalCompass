"""
Auto-detects the best available Gemini model for the API key.
Tries models in preference order, returns the first one that works.
"""
import os

PREFERRED_MODELS = [
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite", 
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-pro",
    "gemini-1.0-pro",
]

_resolved_model = None

def get_gemini_model():
    """Returns a working GenerativeModel, auto-detecting the best available."""
    global _resolved_model
    if _resolved_model is not None:
        return _resolved_model

    import google.generativeai as genai
    from dotenv import load_dotenv
    load_dotenv()

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in .env")

    genai.configure(api_key=api_key)

    # If user explicitly set a model, try that first
    explicit = os.getenv("GEMINI_MODEL", "").strip()
    if explicit:
        PREFERRED_MODELS.insert(0, explicit)

    # Try each model
    for model_name in PREFERRED_MODELS:
        try:
            model = genai.GenerativeModel(model_name)
            # Quick test
            model.generate_content("Hi", 
                generation_config={"max_output_tokens": 5})
            print(f"[gemini] Using model: {model_name}")
            _resolved_model = model
            return model
        except Exception as e:
            err = str(e)
            if "404" in err or "not found" in err.lower() or "not supported" in err.lower():
                print(f"[gemini] {model_name} not available, trying next...")
                continue
            # Other errors (auth, quota) — raise immediately
            raise

    # Last resort: list available models and pick first flash
    try:
        available = [
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in m.supported_generation_methods
            and "flash" in m.name.lower()
        ]
        if available:
            model = genai.GenerativeModel(available[0])
            print(f"[gemini] Auto-selected: {available[0]}")
            _resolved_model = model
            return model
    except Exception:
        pass

    raise RuntimeError(
        "No working Gemini model found. Run: python -c \""
        "import google.generativeai as genai; genai.configure(api_key='YOUR_KEY'); "
        "[print(m.name) for m in genai.list_models()]\""
    )