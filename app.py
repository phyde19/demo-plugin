"""
Demo plugin service for Compass Hub.

Single-file plugin that demonstrates the streaming contract:
  POST /plugin/response  ->  application/x-ndjson

Frame helpers (text, source, error) abstract the NDJSON wire format
so plugin authors never hand-build frame dicts.
"""

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from openai import AsyncAzureOpenAI
from pydantic_settings import BaseSettings, SettingsConfigDict


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    azure_openai_endpoint: str
    azure_openai_api_key: str
    azure_openai_api_version: str = "2024-12-01-preview"
    azure_openai_deployment: str


settings = Settings()

client = AsyncAzureOpenAI(
    azure_endpoint=settings.azure_openai_endpoint,
    api_key=settings.azure_openai_api_key,
    api_version=settings.azure_openai_api_version,
)


# ---------------------------------------------------------------------------
# Frame helpers — the whole point
# ---------------------------------------------------------------------------

def text(*, content: str) -> str:
    """LLM text chunk frame."""
    return json.dumps({"type": "llm", "content": content}) + "\n"


def web_source(
    *,
    index: int,
    title: str,
    url: str,
    snippet: str | None = None,
) -> str:
    """Web citation frame."""
    body: dict[str, Any] = {
        "type": "web",
        "index": index,
        "title": title,
        "url": url,
    }
    if snippet is not None:
        body["snippet"] = snippet
    return json.dumps({"type": "citation", "content": body}) + "\n"


def doc_source(
    *,
    index: int,
    title: str,
    content: str,
    document_ref: str,
    relevance_score: float | None = None,
    preview: str | None = None,
) -> str:
    """Document citation frame."""
    body: dict[str, Any] = {
        "type": "document",
        "index": index,
        "title": title,
        "content": content,
        "document_ref": document_ref,
    }
    if relevance_score is not None:
        body["relevance_score"] = relevance_score
    if preview is not None:
        body["preview"] = preview
    return json.dumps({"type": "citation", "content": body}) + "\n"


def error(
    *,
    message: str,
    code: str = "PLUGIN_ERROR",
    retryable: bool = False,
) -> str:
    """Error frame."""
    return json.dumps({
        "type": "error",
        "content": {"code": code, "message": message, "retryable": retryable},
    }) + "\n"


# ---------------------------------------------------------------------------
# Plugin
# ---------------------------------------------------------------------------

async def stream(request: dict[str, Any]):
    """Stream NDJSON frames for a Compass Hub plugin request."""
    conversation = request.get("conversation", [])
    instructions = request.get("instructions", "")

    messages: list[dict[str, str]] = []
    if instructions:
        messages.append({"role": "system", "content": instructions})
    for msg in request.get("conversation_seed", []):
        messages.append({"role": msg["role"], "content": msg["content"]})
    for msg in conversation:
        messages.append({"role": msg["role"], "content": msg["content"]})

    # --- Stream LLM response ---
    try:
        response = await client.chat.completions.create(
            model=settings.azure_openai_deployment,
            messages=messages,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield text(content=delta.content)
    except Exception as exc:
        yield error(message=f"LLM request failed: {exc}", code="LLM_ERROR", retryable=True)
        return

    # --- Stream sources ---
    yield doc_source(index=1, title="Architecture Guide", content="The platform uses event-driven microservices with a central message bus.", document_ref="architecture-guide-v3.pdf", relevance_score=0.95)
    yield doc_source(index=2, title="Data Model Spec", content="All entities use UUID primary keys with created_at/updated_at timestamps.", document_ref="data-model-spec.docx", preview="Section 2: Entity Design")
    yield web_source(index=3, title="API Reference", url="https://docs.internal/api", snippet="See section 4.2")
    yield web_source(index=4, title="Incident Playbook", url="https://docs.internal/incidents", snippet="Escalation workflow")

    # --- Uncomment to demo error streaming ---
    # yield error(message="Something went wrong!", code="DEMO_ERROR", retryable=False)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Demo Plugin")


@app.post("/plugin/response")
async def plugin_response(request: Request):
    body = await request.json()
    return StreamingResponse(stream(body), media_type="application/x-ndjson")


@app.get("/")
async def health():
    return {"status": "ok", "service": "demo-plugin"}
