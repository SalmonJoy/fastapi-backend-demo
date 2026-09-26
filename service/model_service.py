import json
import os
from json import JSONDecodeError
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException


OLLAMA_HOST = "http://localhost:11434"
OLLAMA_CLOUD_BASE_URL = "https://ollama.com/v1"
GEMINI_MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
REQUEST_TIMEOUT_SECONDS = 10


def load_env_file():
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def get_json(url, headers=None):
    request = Request(url, headers=headers or {"Accept": "application/json"})

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return {
                "ok": True,
                "data": json.loads(response.read().decode("utf-8")),
            }
    except JSONDecodeError:
        return {"ok": False, "error": "Provider returned an invalid JSON response"}
    except HTTPError as error:
        return {
            "ok": False,
            "status_code": error.code,
            "error": error.read().decode("utf-8", errors="replace"),
        }
    except URLError as error:
        return {"ok": False, "error": str(error.reason)}


def post_json(url, payload, headers=None):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            **(headers or {}),
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return {
                "ok": True,
                "data": json.loads(response.read().decode("utf-8")),
            }
    except JSONDecodeError:
        return {"ok": False, "error": "Provider returned an invalid JSON response"}
    except HTTPError as error:
        return {
            "ok": False,
            "status_code": error.code,
            "error": error.read().decode("utf-8", errors="replace"),
        }
    except URLError as error:
        return {"ok": False, "error": str(error.reason)}


def get_ollama_local_capabilities(host, model_name, headers):
    result = post_json(f"{host}/api/show", {"model": model_name}, headers=headers)

    if not result["ok"]:
        return []

    return result["data"].get("capabilities", [])


def model_supports_generate(capabilities):
    return "completion" in capabilities


def list_ollama_local_models():
    host = os.getenv("OLLAMA_HOST", OLLAMA_HOST).rstrip("/")
    headers = {"Accept": "application/json"}
    api_key = os.getenv("OLLAMA_API_KEY")

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    result = get_json(f"{host}/api/tags", headers=headers)

    if result["ok"]:
        models = []

        for model in result["data"].get("models", []):
            model_name = model.get("name") or model.get("model")
            capabilities = get_ollama_local_capabilities(host, model_name, headers)
            model["capabilities"] = capabilities
            model["supports_generate"] = model_supports_generate(capabilities)
            models.append(model)

        result["data"]["models"] = models

    return {
        "provider": "ollama",
        "type": "local",
        "configured": True,
        "host": host,
        **result,
    }


def list_ollama_cloud_models():
    api_key = os.getenv("OLLAMA_API_KEY")

    if not api_key:
        return {
            "provider": "ollama",
            "type": "cloud",
            "configured": False,
            "models": [],
        }

    base_url = os.getenv("OLLAMA_CLOUD_BASE_URL", OLLAMA_CLOUD_BASE_URL).rstrip("/")
    result = get_json(
        f"{base_url}/models",
        headers={
            "Accept": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )

    if not result["ok"]:
        return {
            "provider": "ollama",
            "type": "cloud",
            "configured": True,
            "host": base_url,
            **result,
        }

    models = [
        {
            "name": model.get("id"),
            "model": model.get("id"),
            "supports_generate": True,
            "details": model,
        }
        for model in result["data"].get("data", [])
    ]

    return {
        "provider": "ollama",
        "type": "cloud",
        "configured": True,
        "host": base_url,
        "ok": True,
        "data": {"models": models},
    }


def list_gemini_models():
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        return {
            "provider": "gemini",
            "type": "cloud",
            "configured": False,
            "models": [],
        }

    models = []
    page_token = None

    while True:
        query = {"key": api_key, "pageSize": 1000}
        if page_token:
            query["pageToken"] = page_token

        result = get_json(f"{GEMINI_MODELS_URL}?{urlencode(query)}")
        if not result["ok"]:
            return {
                "provider": "gemini",
                "type": "cloud",
                "configured": True,
                **result,
            }

        data = result["data"]
        models.extend(data.get("models", []))
        page_token = data.get("nextPageToken")

        if not page_token:
            break

    return {
        "provider": "gemini",
        "type": "cloud",
        "configured": True,
        "ok": True,
        "data": {
            "models": [
                {
                    **model,
                    "supports_generate": "generateContent"
                    in model.get("supportedGenerationMethods", []),
                }
                for model in models
            ]
        },
    }


def list_available_models():
    load_env_file()
    providers = [
        list_ollama_local_models(),
        list_ollama_cloud_models(),
        list_gemini_models(),
    ]
    models = []

    for provider in providers:
        if not provider.get("ok"):
            continue

        models.extend(
            {
                "provider": provider["provider"],
                "type": provider["type"],
                "name": model.get("name"),
                "supports_generate": model.get("supports_generate", True),
                "details": model,
            }
            for model in provider.get("data", {}).get("models", [])
        )

    if not models and all(not provider.get("ok") for provider in providers):
        raise HTTPException(
            status_code=503,
            detail="No configured model provider returned models",
        )

    return {"models": models, "providers": providers}
