from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

from docling.document_converter import DocumentConverter

logger = logging.getLogger("doc_decision.docling")

MAX_EVIDENCE_CHARS = 16_000


class DoclingProcessor:

    def __init__(self):
        logger.info("Initializing Docling...")
        self.converter = DocumentConverter()
        logger.info("Docling initialized.")

    def _extract_structured_evidence(
        self,
        document: Any,
    ) -> dict[str, Any]:
        """Extract deterministic document facts from Docling output."""

        markdown = document.export_to_markdown()
        upper_text = markdown.upper()

        # ---------------------------------------------------------
        # Tables
        # ---------------------------------------------------------
        tables: list[dict[str, Any]] = []

        for index, table in enumerate(document.tables):
            try:
                dataframe = table.export_to_dataframe(doc=document)

                rows = dataframe.fillna("").astype(str).to_dict(
                    orient="records"
                )

                tables.append(
                    {
                        "index": index,
                        "rows": rows,
                        "markdown": table.export_to_markdown(
                            doc=document
                        ),
                    }
                )
            except Exception:
                logger.exception(
                    "Failed to export Docling table %d",
                    index,
                )

        # ---------------------------------------------------------
        # Invoice number
        # ---------------------------------------------------------
        invoice_number = None

        invoice_match = re.search(
            r"\bINVOICE\s*(?:#|NUMBER|NO\.?)?\s*[:#-]?\s*"
            r"([A-Z0-9][A-Z0-9./_-]*)",
            upper_text,
        )

        if invoice_match:
            invoice_number = invoice_match.group(1).strip()

        # ---------------------------------------------------------
        # Purchase order references
        # ---------------------------------------------------------
        po_patterns = [
            r"\bP\.\s*O\.\s*(?:NUMBER|NO\.?|#)?\s*[:#-]?\s*"
            r"([A-Z0-9]+(?:[-/][A-Z0-9]+)+)\b",

            r"\bPURCHASE\s+ORDER\s*(?:NUMBER|NO\.?|#)?\s*[:#-]?\s*"
            r"([A-Z0-9]+(?:[-/][A-Z0-9]+)+)\b",
        ]

        po_references: list[str] = []

        for pattern in po_patterns:
            for match in re.finditer(pattern, upper_text):
                value = match.group(1).strip()

                if value not in po_references:
                    po_references.append(value)

        # ---------------------------------------------------------
        # Payment terms
        # ---------------------------------------------------------
        payment_terms = None

        payment_terms_patterns = [
            r"\bDUE\s+AFTER\s+\d+\s+DAYS?\b",
            r"\bNET\s+\d+\b",
            r"\bDUE\s+ON\s+[A-Z0-9./ -]+\b",
        ]

        for pattern in payment_terms_patterns:
            match = re.search(pattern, upper_text)

            if match:
                payment_terms = match.group(0).strip()
                break

        # ---------------------------------------------------------
        # Tax
        # ---------------------------------------------------------
        tax_detected = bool(
            re.search(
                r"\b(?:SALES\s+TAX|VAT|GST|TAX)\b",
                upper_text,
            )
        )

        # ---------------------------------------------------------
        # Total amount
        # ---------------------------------------------------------
        total_amount = None
        total_currency = None

        total_patterns = [
            r"\bTOTAL\s+DUE\b\s*[:#-]?\s*"
            r"(?:USD\s*)?([$€£₹]?\s?[\d,]+(?:\.\d{2})?)",

            r"\bAMOUNT\s+DUE\b\s*[:#-]?\s*"
            r"(?:USD\s*)?([$€£₹]?\s?[\d,]+(?:\.\d{2})?)",

            r"\bGRAND\s+TOTAL\b\s*[:#-]?\s*"
            r"(?:USD\s*)?([$€£₹]?\s?[\d,]+(?:\.\d{2})?)",

            r"\bTOTAL\s+AMOUNT\b\s*[:#-]?\s*"
            r"(?:USD\s*)?([$€£₹]?\s?[\d,]+(?:\.\d{2})?)",
        ]

        for pattern in total_patterns:
            match = re.search(pattern, upper_text)

            if not match:
                continue

            raw = match.group(1).replace(",", "").strip()

            symbol = (
                raw[:1]
                if raw[:1] in "$€£₹"
                else None
            )

            number = (
                raw[1:].strip()
                if symbol
                else raw
            )

            try:
                total_amount = float(number)
                total_currency = symbol
                break
            except ValueError:
                continue

        # ---------------------------------------------------------
        # Vendor information
        # ---------------------------------------------------------
        vendor_name = None

        # Basic deterministic extraction for common invoice layout.
        # Jev will still make the semantic "has vendor information"
        # decision.
        if "INVOICE" in upper_text:
            lines = [
                line.strip()
                for line in markdown.splitlines()
                if line.strip()
            ]

            for line in lines[:20]:
                normalized = line.upper()

                if normalized in {
                    "INVOICE",
                    "INVOICE NUMBER",
                }:
                    continue

                if (
                    "INVOICE #" not in normalized
                    and "INVOICE NUMBER" not in normalized
                    and not normalized.startswith("DATE")
                    and not normalized.startswith("TO:")
                    and len(line) > 2
                ):
                    vendor_name = line
                    break

        # ---------------------------------------------------------
        # Line items
        # ---------------------------------------------------------
        line_items_detected = False

        for table in tables:
            table_text = table["markdown"].upper()

            if (
                "QUANTITY" in table_text
                or "DESCRIPTION" in table_text
                or "UNIT PRICE" in table_text
            ):
                line_items_detected = True
                break

        return {
            "invoice_number": invoice_number,
            "purchase_order_reference_detected": bool(
                po_references
            ),
            "purchase_order_references": po_references[:10],
            "payment_terms": payment_terms,
            "tax_detected": tax_detected,
            "total_amount": total_amount,
            "total_currency": total_currency,
            "vendor_name": vendor_name,
            "line_items_detected": line_items_detected,
            "table_count": len(tables),
            "tables": tables,
        }

    def parse_document(
        self,
        file_path: Path,
    ) -> dict:
        logger.info(
            "Converting document with Docling: %s",
            file_path,
        )

        result = self.converter.convert(
            file_path,
            max_file_size=20 * 1024 * 1024,
        )

        if result.document is None:
            logger.error(
                "Docling did not produce a document for %s",
                file_path,
            )
            raise RuntimeError(
                "Docling did not produce a document."
            )

        document = result.document

        markdown = document.export_to_markdown()

        structured_evidence = self._extract_structured_evidence(
            document
        )

        logger.info(
            "Docling conversion succeeded for %s: "
            "status=%s markdown_chars=%d tables=%d",
            file_path,
            result.status,
            len(markdown),
            structured_evidence["table_count"],
        )

        return {
            "markdown": markdown[:MAX_EVIDENCE_CHARS],
            "full_markdown": markdown,
            "structured_evidence": structured_evidence,
            "source": str(file_path),
            "status": str(result.status),
        }