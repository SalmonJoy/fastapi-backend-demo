import hashlib
import json
import os
import re
from json import JSONDecodeError
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import HTTPException

from service.model_service import OLLAMA_HOST, load_env_file
from service.pinecone_service import list_pinecone_indexes, request_json


DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 150
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_BATCH_SIZE = 100
EMBED_TIMEOUT_SECONDS = 60


def normalize_text(text):
    return re.sub(r"\s+", " ", text).strip()


def chunk_text(text, chunk_size=DEFAULT_CHUNK_SIZE, chunk_overlap=DEFAULT_CHUNK_OVERLAP):
    text = normalize_text(text)

    if not text:
        raise HTTPException(status_code=400, detail="text is required")

    if chunk_size < 100:
        raise HTTPException(status_code=400, detail="chunk_size must be at least 100")

    if chunk_overlap < 0 or chunk_overlap >= chunk_size:
        raise HTTPException(
            status_code=400,
            detail="chunk_overlap must be greater than or equal to 0 and less than chunk_size",
        )

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))

        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        next_start = max(end - chunk_overlap, 0)
        start = next_start if next_start > start else end

    return chunks


def post_json(url, payload, headers=None, timeout=EMBED_TIMEOUT_SECONDS):
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
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except JSONDecodeError as error:
        raise HTTPException(
            status_code=502,
            detail="Provider returned an invalid JSON response",
        ) from error
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise HTTPException(status_code=error.code, detail=detail) from error
    except URLError as error:
        raise HTTPException(
            status_code=503,
            detail=f"Could not connect to provider: {error.reason}",
        ) from error


def embed_chunks(chunks, expected_dimension=None):
    host = os.getenv("OLLAMA_HOST", OLLAMA_HOST).rstrip("/")
    model = os.getenv("OLLAMA_EMBED_MODEL", DEFAULT_EMBED_MODEL)
    payload = {
        "model": model,
        "input": chunks,
    }
    data = post_json(f"{host}/api/embed", payload)
    embeddings = data.get("embeddings", [])

    if len(embeddings) != len(chunks):
        raise HTTPException(
            status_code=502,
            detail="Embedding count did not match chunk count",
        )

    expected_dimension = expected_dimension or os.getenv("PINECONE_EXPECTED_DIMENSION")
    if expected_dimension:
        try:
            expected_dimension = int(expected_dimension)
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail="Expected embedding dimension must be an integer",
            ) from error

        dimensions = {len(embedding) for embedding in embeddings}

        if dimensions != {expected_dimension}:
            raise HTTPException(
                status_code=400,
                detail=f"Embedding dimension {sorted(dimensions)} does not match expected Pinecone dimension {expected_dimension}",
            )

    return model, embeddings


def get_index(index_name):
    for index in list_pinecone_indexes():
        if index.get("name") == index_name:
            if not index.get("host"):
                raise HTTPException(
                    status_code=400,
                    detail=f"Pinecone index {index_name} does not have a host",
                )

            return index

    raise HTTPException(
        status_code=404,
        detail=f"Pinecone index {index_name} was not found",
    )


def create_vectors(chunks, embeddings, index_name, namespace_name, embed_model):
    source_hash = hashlib.sha256("\n".join(chunks).encode("utf-8")).hexdigest()
    vectors = []

    for chunk_index, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
        chunk_hash = hashlib.sha256(chunk.encode("utf-8")).hexdigest()[:16]
        vector_id = f"{source_hash[:16]}-{chunk_index}-{chunk_hash}"
        vectors.append(
            {
                "id": vector_id,
                "values": embedding,
                "metadata": {
                    "text": chunk,
                    "chunk_index": chunk_index,
                    "chunk_count": len(chunks),
                    "source_hash": source_hash,
                    "index_name": index_name,
                    "namespace": namespace_name,
                    "embedding_model": embed_model,
                },
            }
        )

    return vectors


def upsert_vectors(index_host, namespace_name, vectors):
    batch_size = int(os.getenv("PINECONE_BATCH_SIZE", DEFAULT_BATCH_SIZE))
    upserted_count = 0
    batches = []

    for start in range(0, len(vectors), batch_size):
        batch = vectors[start : start + batch_size]
        response = request_json(
            f"https://{index_host}/vectors/upsert",
            method="POST",
            payload={
                "vectors": batch,
                "namespace": namespace_name,
            },
        )
        batch_count = response.get("upsertedCount", response.get("upserted_count", len(batch)))
        upserted_count += batch_count
        batches.append(
            {
                "batch_index": len(batches),
                "requested_count": len(batch),
                "upserted_count": batch_count,
            }
        )

    return upserted_count, batches


def ingest_text_to_pinecone(
    text,
    index_name,
    namespace_name,
    chunk_size=DEFAULT_CHUNK_SIZE,
    chunk_overlap=DEFAULT_CHUNK_OVERLAP,
):
    load_env_file()

    if not index_name:
        raise HTTPException(status_code=400, detail="index_name is required")

    if not namespace_name:
        raise HTTPException(status_code=400, detail="namespace_name is required")

    namespace_name = "" if namespace_name == "__default__" else namespace_name
    index = get_index(index_name)
    chunks = chunk_text(text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    embed_model, embeddings = embed_chunks(chunks, expected_dimension=index.get("dimension"))
    vectors = create_vectors(chunks, embeddings, index_name, namespace_name, embed_model)
    upserted_count, batches = upsert_vectors(index["host"], namespace_name, vectors)

    return {
        "index_name": index_name,
        "namespace_name": namespace_name or "__default__",
        "embedding_model": embed_model,
        "chunk_count": len(chunks),
        "upserted_count": upserted_count,
        "batches": batches,
        "vector_ids": [vector["id"] for vector in vectors],
    }
