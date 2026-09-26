import json
import os
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from fastapi import HTTPException

from service.model_service import (
    OLLAMA_CLOUD_BASE_URL,
    OLLAMA_HOST,
    REQUEST_TIMEOUT_SECONDS,
    load_env_file,
)


GEMINI_API_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


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
            return json.loads(response.read().decode("utf-8"))
    except JSONDecodeError as error:
        raise HTTPException(
            status_code=502,
            detail="Provider returned an invalid JSON response",
        ) from error
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise HTTPException(
            status_code=error.code,
            detail=detail,
        ) from error
    except URLError as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to provider: {error.reason}",
        ) from error


def normalize_source(provider, model_type=None):
    provider = provider.strip().lower()
    model_type = model_type.strip().lower() if model_type else None

    if provider == "gemini":
        return "gemini", "cloud"

    if provider == "ollama-cloud":
        return "ollama", "cloud"

    if provider == "ollama-local":
        return "ollama", "local"

    if provider == "ollama" and model_type in {"cloud", "local"}:
        return "ollama", model_type

    raise HTTPException(
        status_code=400,
        detail="provider must be gemini, ollama-cloud, ollama-local, or ollama with type cloud/local",
    )


def generate_with_ollama_local(model, text):
    host = os.getenv("OLLAMA_HOST", OLLAMA_HOST).rstrip("/")
    headers = {}
    api_key = os.getenv("OLLAMA_API_KEY")

    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    model_info = post_json(f"{host}/api/show", {"model": model}, headers=headers)
    capabilities = model_info.get("capabilities", [])

    if "completion" not in capabilities:
        raise HTTPException(
            status_code=400,
            detail=f"{model} does not support text generation",
        )

    payload = {
        "model": model,
        "prompt": text,
        "stream": False,
    }
    data = post_json(f"{host}/api/generate", payload, headers=headers)

    return {
        "output": data.get("response", ""),
        "raw": data,
    }


def generate_with_ollama_cloud(model, text):
    api_key = os.getenv("OLLAMA_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="OLLAMA_API_KEY is required for Ollama cloud",
        )

    base_url = os.getenv("OLLAMA_CLOUD_BASE_URL", OLLAMA_CLOUD_BASE_URL).rstrip("/")
    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": text,
            }
        ],
    }
    data = post_json(
        f"{base_url}/chat/completions",
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    choices = data.get("choices", [])
    output = choices[0].get("message", {}).get("content", "") if choices else ""

    return {
        "output": output,
        "raw": data,
    }


def generate_with_gemini(model, text):
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="GEMINI_API_KEY is required for Gemini",
        )

    model_name = model if model.startswith("models/") else f"models/{model}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": text,
                    }
                ]
            }
        ]
    }
    query = urlencode({"key": api_key})
    data = post_json(
        f"{GEMINI_API_BASE_URL}/{quote(model_name, safe='/')}:generateContent?{query}",
        payload,
    )
    candidates = data.get("candidates", [])
    parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
    output = "".join(part.get("text", "") for part in parts)

    return {
        "output": output,
        "raw": data,
    }


def generate_text(provider, model, text, model_type=None):
    load_env_file()
    normalized_provider, normalized_type = normalize_source(provider, model_type)

    if normalized_provider == "gemini":
        result = generate_with_gemini(model, text)
    elif normalized_type == "cloud":
        result = generate_with_ollama_cloud(model, text)
    else:
        result = generate_with_ollama_local(model, text)

    return {
        "provider": normalized_provider,
        "type": normalized_type,
        "model": model,
        "output": result["output"],
        "raw": result["raw"],
    }
