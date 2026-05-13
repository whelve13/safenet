import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.schemas import (
    AnalyzeBatchRequest,
    AnalyzeBatchResponse,
    AnalyzeTextRequest,
    AnalyzeTextResponse,
)
from src.database.repository import DatabaseRepository
from src.models.config import AnalysisConfig
from src.services.moderation_service import ModerationService


DB_PATH = os.getenv("SAFENET_DB_PATH", "safenet.db")
SCORING_MODE = os.getenv("SAFENET_SCORING_MODE", "hybrid_model_priority")

app = FastAPI(title="SafeNet API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

repo = DatabaseRepository(DB_PATH)
moderation_service = ModerationService(AnalysisConfig(scoring_mode=SCORING_MODE))


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "database": DB_PATH}


@app.get("/model-info")
def model_info() -> dict:
    analyzer = moderation_service.analyzer
    hf_model = analyzer.hf_model
    return {
        "dictionary_enabled": True,
        "hf_model_enabled": analyzer.config.use_hf_model,
        "hf_model_name": hf_model.model_name,
        "hf_model_loaded": hf_model.is_loaded,
        "hf_load_error": hf_model.load_error,
        "scoring_mode": analyzer.config.scoring_mode,
        "hybrid_dictionary_weight": analyzer.config.hybrid_dictionary_weight,
        "hf_fallback_threshold": analyzer.config.hf_fallback_threshold,
    }


@app.post("/v1/analyze/text", response_model=AnalyzeTextResponse)
def analyze_text(payload: AnalyzeTextRequest) -> dict:
    result = moderation_service.analyze_text(payload.text)
    persisted_event = False

    if payload.persist_event_on_action and moderation_service.should_persist_event(result["decision"]):
        event = moderation_service.build_event(result, source=payload.source, page_url=payload.page_url)
        persisted_event = repo.save_moderation_event(event, dedupe_window_seconds=30)

    result["persisted_event"] = persisted_event
    return result


@app.post("/v1/analyze/batch", response_model=AnalyzeBatchResponse)
def analyze_batch(payload: AnalyzeBatchRequest) -> dict:
    texts = [item.text for item in payload.items]
    analyzed = moderation_service.analyze_batch(texts)
    results = []

    for item, result in zip(payload.items, analyzed):
        persisted_event = False
        if payload.persist_event_on_action and moderation_service.should_persist_event(result["decision"]):
            event = moderation_service.build_event(result, source=item.source, page_url=item.page_url)
            persisted_event = repo.save_moderation_event(event, dedupe_window_seconds=30)

        result["persisted_event"] = persisted_event
        results.append(result)

    return {"count": len(results), "results": results}

