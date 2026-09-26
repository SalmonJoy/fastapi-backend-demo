# Simple FastAPI App

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Run

```powershell
uvicorn main:app --reload
```

Open:

- http://127.0.0.1:8000/
- http://127.0.0.1:8000/api
- http://127.0.0.1:8000/health
- http://127.0.0.1:8000/models
- http://127.0.0.1:8000/pinecone/indexes
- http://127.0.0.1:8000/pinecone/upsert-text
- http://127.0.0.1:8000/generate.html
- http://127.0.0.1:8000/ingest.html

The homepage `/` serves the static models dashboard.
The `/generate.html` page uses `POST /generate` to send text to a selected model.
The `/ingest.html` page uses `POST /pinecone/upsert-text` to embed and store text in Pinecone.
Embedding-only models are still visible on the dashboard, but they are hidden from the generation page.

## Model Providers

The `/models` endpoint lists local Ollama models and configured cloud models.

It reads these optional values from `.env`:

```powershell
OLLAMA_HOST=http://localhost:11434
OLLAMA_API_KEY=your-api-key
OLLAMA_CLOUD_BASE_URL=https://ollama.com/v1
GEMINI_API_KEY=your-gemini-api-key
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_API_VERSION=2025-10
```

Response shape:

```json
{
  "models": [
    {
      "provider": "ollama",
      "type": "local",
      "name": "llama3.2:latest",
      "details": {}
    },
    {
      "provider": "gemini",
      "type": "cloud",
      "name": "models/gemini-1.5-flash",
      "details": {}
    }
  ],
  "providers": []
}
```

## Generate Text

Send text to a selected model with `POST /generate`.

```json
{
  "provider": "ollama-cloud",
  "model": "gpt-oss:20b-cloud",
  "text": "Explain FastAPI in one sentence."
}
```

Provider options:

- `gemini`
- `ollama-cloud`
- `ollama-local`

You can also use:

```json
{
  "provider": "ollama",
  "type": "local",
  "model": "llama3.2:latest",
  "text": "Hello"
}
```

## Pinecone Indexes

List Pinecone indexes and their namespaces with `GET /pinecone/indexes`.

Response shape:

```json
{
  "indexes": [
    {
      "name": "example-index",
      "host": "example-index-project.svc.region.pinecone.io",
      "namespaces": [
        {
          "name": "default",
          "vector_count": 100
        }
      ]
    }
  ],
  "total_indexes": 1
}
```

## Pinecone Text Ingestion

Chunk text, embed each chunk with Ollama, and upsert vectors to Pinecone with `POST /pinecone/upsert-text`.

```json
{
  "text": "Long text to store in Pinecone.",
  "index_name": "rag-demo",
  "namespace_name": "demo-pdf",
  "chunk_size": 1000,
  "chunk_overlap": 150
}
```

The API uses:

- `OLLAMA_HOST`
- `OLLAMA_EMBED_MODEL`
- `PINECONE_API_KEY`
- `PINECONE_BATCH_SIZE`
- `PINECONE_EXPECTED_DIMENSION`

Metadata stored with each vector includes chunk text, chunk index, chunk count, source hash, namespace, index name, and embedding model.
