from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentAnalysisResponse(BaseModel):
    filename: str
    document_type: str
    document_type_probabilities: dict[str, float]
    department: str
    department_probabilities: dict[str, float]
    is_business_document_probability: float = Field(ge=0.0, le=1.0)
    requires_human_review_probability: float = Field(ge=0.0, le=1.0)
    action: str
    extracted_text: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    jev: dict[str, Any] = Field(default_factory=dict)
