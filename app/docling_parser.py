from __future__ import annotations

import logging
from pathlib import Path

from docling.document_converter import DocumentConverter


logger = logging.getLogger("doc_decision.docling")
MAX_EVIDENCE_CHARS = 16_000


class DoclingProcessor:

    def __init__(self):
        logger.info("Initializing Docling...")

        self.converter = DocumentConverter()

        logger.info("Docling initialized.")

    def parse_document(
        self,
        file_path: Path,
    ) -> dict:
        logger.info("Converting document with Docling: %s", file_path)

        result = self.converter.convert(
            file_path,
            max_file_size=20 * 1024 * 1024,
        )

        if result.document is None:
            logger.error("Docling did not produce a document for %s", file_path)
            raise RuntimeError(
                "Docling did not produce a document."
            )

        document = result.document

        markdown = document.export_to_markdown()
        logger.info(
            "Docling conversion succeeded for %s: status=%s markdown_chars=%d",
            file_path,
            result.status,
            len(markdown),
        )

        return {
            "markdown": markdown[:MAX_EVIDENCE_CHARS],
            "full_markdown": markdown,
            "tables": [...],
            "source": str(file_path),
            "status": str(result.status),
        }