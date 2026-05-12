from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class DetectionExplanation(BaseModel):
    contributors: List[str]
    scoring_method: str
    dict_score: float
    hf_score: Optional[float] = None
    reason: str


class AnalyzeTextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    source: str = Field(default="extension", max_length=50)
    page_url: Optional[str] = Field(default=None, max_length=500)
    persist_event_on_action: bool = False


class AnalyzeBatchItem(BaseModel):
    text: str = Field(..., min_length=1, max_length=500)
    source: str = Field(default="extension", max_length=50)
    page_url: Optional[str] = Field(default=None, max_length=500)


class AnalyzeBatchRequest(BaseModel):
    items: List[AnalyzeBatchItem] = Field(..., min_length=1, max_length=100)
    persist_event_on_action: bool = False


class AnalyzeTextResponse(BaseModel):
    snippet: str
    toxicity_score: float
    severity: Literal["low", "medium", "high", "critical"]
    decision: Literal["allow", "blur", "block"]
    detection_method: Literal["dictionary", "toxic-bert", "hybrid"]
    explanation: DetectionExplanation
    persisted_event: bool = False


class AnalyzeBatchResponse(BaseModel):
    count: int
    results: List[AnalyzeTextResponse]

