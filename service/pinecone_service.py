import json
import os
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException

from service.model_service import REQUEST_TIMEOUT_SECONDS, load_env_file


PINECONE_CONTROL_PLANE_URL = "https://api.pinecone.io"
PINECONE_API_VERSION = "2025-10"


def pinecone_headers():
    api_key = os.getenv("PINECONE_API_KEY")

    if not api_key:
        raise HTTPException(
            status_code=400,
            detail="PINECONE_API_KEY is required",
        )

    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Api-Key": api_key,
        "X-Pinecone-Api-Version": os.getenv(
            "PINECONE_API_VERSION",
            PINECONE_API_VERSION,
        ),
    }


def request_json(url, method="GET", payload=None):
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=pinecone_headers(),
        method=method,
    )

    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except JSONDecodeError as error:
        raise HTTPException(
            status_code=502,
            detail="Pinecone returned an invalid JSON response",
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
            detail=f"Could not connect to Pinecone: {error.reason}",
        ) from error


def list_pinecone_indexes():
    control_plane_url = os.getenv(
        "PINECONE_CONTROL_PLANE_URL",
        PINECONE_CONTROL_PLANE_URL,
    ).rstrip("/")
    response = request_json(f"{control_plane_url}/indexes")

    return response.get("indexes", [])


def describe_index_namespaces(index):
    host = index.get("host")

    if not host:
        return {
            "ok": False,
            "error": "Index host is missing",
            "namespaces": [],
        }

    try:
        stats = request_json(f"https://{host}/describe_index_stats", method="POST", payload={})
    except HTTPException as error:
        return {
            "ok": False,
            "error": error.detail,
            "namespaces": [],
        }

    namespaces = [
        {
            "name": name or "__default__",
            "vector_count": details.get("vector_count", 0),
        }
        for name, details in stats.get("namespaces", {}).items()
    ]

    return {
        "ok": True,
        "dimension": stats.get("dimension"),
        "index_fullness": stats.get("index_fullness"),
        "total_vector_count": stats.get("total_vector_count"),
        "namespaces": namespaces,
    }


def list_indexes_with_namespaces():
    load_env_file()
    indexes = []

    for index in list_pinecone_indexes():
        namespace_details = describe_index_namespaces(index)
        indexes.append(
            {
                "name": index.get("name"),
                "host": index.get("host"),
                "metric": index.get("metric"),
                "dimension": index.get("dimension"),
                "status": index.get("status"),
                "spec": index.get("spec"),
                "namespaces": namespace_details["namespaces"],
                "namespace_status": {
                    key: value
                    for key, value in namespace_details.items()
                    if key != "namespaces"
                },
                "details": index,
            }
        )

    return {
        "indexes": indexes,
        "total_indexes": len(indexes),
    }
