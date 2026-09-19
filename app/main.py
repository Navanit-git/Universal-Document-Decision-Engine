from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
import os
import tempfile

from fastapi import FastAPI, File, HTTPException, UploadFile
from starlette.concurrency import run_in_threadpool

from app import logger
from app.docling_parser import DoclingProcessor
from app.jev import evaluate_document
from app.router import decide_action
from app.schemas import DocumentAnalysisResponse

from dotenv import load_dotenv
load_dotenv()

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting DocDecision...")
    logger.info("Loading Docling/OCR models...")
    app.state.docling = DoclingProcessor()
    logger.info("DocDecision ready.")
    yield
    logger.info("Shutting down DocDecision...")


app = FastAPI(
    title="DocDecision",
    description="Universal Document Decision Engine using Docling + Jev",
    version="0.3.0",
    lifespan=lifespan,
)


def process_document(
    file_path: Path,
    filename: str,
    docling_processor: DoclingProcessor,
) -> DocumentAnalysisResponse:
    logger.info("Starting processing for document: %s", filename)
    parsed = docling_processor.parse_document(file_path)
    logger.info(
        "Docling parsed %s: source=%s status=%s markdown_chars=%d",
        filename,
        parsed["source"],
        parsed["status"],
        len(parsed["full_markdown"]),
    )

    jev_result = evaluate_document(
            document_text=parsed["markdown"],
            structured_evidence=parsed.get("structured_evidence", {}),
        )
    action = decide_action(jev_result)

    core = jev_result["core"]
    choices = core["choices"]
    nouls = core["nouls"]

    document_type = choices["document_type"]["value"]
    department = choices["department"]["value"]

    logger.info(
        "Document classification complete for %s: type=%s department=%s action=%s",
        filename,
        document_type,
        department,
        action,
    )

    return DocumentAnalysisResponse(
        filename=filename,
        document_type=document_type,
        document_type_probabilities=choices["document_type"]["probabilities"],
        department=department,
        department_probabilities=choices["department"]["probabilities"],
        is_business_document_probability=nouls["is_business_document"]["probability"],
        requires_human_review_probability=nouls["requires_human_review"]["probability"],
        action=action,
        extracted_text=parsed["full_markdown"],
        metadata={
            "docling_status": parsed["status"],
            "jev_domain": jev_result["domain"],
            "document_evidence": jev_result["evidence"],
        },
        jev=jev_result,
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=DocumentAnalysisResponse)
async def analyze(file: UploadFile = File(...)) -> DocumentAnalysisResponse:
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    logger.info("Received analysis request for %s (suffix=%s)", filename, suffix)

    if suffix not in ALLOWED_EXTENSIONS:
        logger.warning("Rejected unsupported file type: %s", filename)
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix or 'unknown'}",
        )

    contents = await file.read()
    logger.info("Read %d bytes for %s", len(contents), filename)
    if len(contents) > MAX_UPLOAD_BYTES:
        logger.warning("Rejected oversized upload: %s (%d bytes)", filename, len(contents))
        raise HTTPException(status_code=413, detail="File exceeds 20 MB limit.")

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(contents)
            temp_path = Path(tmp.name)

        logger.info("Starting processing for temporary file %s", temp_path)
        result = await run_in_threadpool(
            process_document,
            temp_path,
            filename,
            app.state.docling,
        )
        logger.info("Completed analysis for %s with action=%s", filename, result.action)
        return result
    except Exception as exc:
        logger.exception("Failed to analyze %s", filename)
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass
