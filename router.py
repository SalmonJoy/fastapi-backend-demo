from fastapi import APIRouter
from pydantic import BaseModel

from service.generation_service import generate_text
from service.ingestion_service import ingest_text_to_pinecone
from service.model_service import list_available_models
from service.pinecone_service import list_indexes_with_namespaces

router = APIRouter()


class GenerateRequest(BaseModel):
    provider: str
    model: str
    text: str
    type: str | None = None


class PineconeIngestRequest(BaseModel):
    text: str
    index_name: str
    namespace_name: str
    chunk_size: int = 1000
    chunk_overlap: int = 150


@router.get("/api")
def read_api_info():
    return {"message": "Hello, This is Salmon Joy!"}


@router.get("/health")
def health_check():
    return {"status": "ok", "info": "The backend is live"}


@router.get("/models")
def get_models():
    return list_available_models()


@router.post("/generate")
def generate(request: GenerateRequest):
    return generate_text(
        provider=request.provider,
        model=request.model,
        text=request.text,
        model_type=request.type,
    )


@router.get("/pinecone/indexes")
def get_pinecone_indexes():
    return list_indexes_with_namespaces()


@router.post("/pinecone/upsert-text")
def upsert_text_to_pinecone(request: PineconeIngestRequest):
    return ingest_text_to_pinecone(
        text=request.text,
        index_name=request.index_name,
        namespace_name=request.namespace_name,
        chunk_size=request.chunk_size,
        chunk_overlap=request.chunk_overlap,
    )
