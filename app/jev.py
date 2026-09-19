from __future__ import annotations

import logging
import re
from typing import Any

from typesafe_sdk import Choice, Noul, Score, TypeSafeClient

logger = logging.getLogger("doc_decision.jev")

DOCUMENT_TYPES = {
    "invoice": "A vendor invoice requesting payment.",
    "receipt": "Evidence of a completed purchase or payment.",
    "purchase_order": "A purchase order authorizing a purchase.",
    "contract": "A legal or commercial agreement between parties.",
    "resume": "A resume or CV describing a person's work history, education, and skills.",
    "form": "A structured form intended to be completed or processed.",
    "report": "A report containing findings, analysis, or business information.",
    "email": "An email or business correspondence document.",
    "memo": "An internal memo or short organizational communication.",
    "specification": "A technical or product specification.",
    "other": "None of the other document types clearly applies.",
}

DEPARTMENTS = {
    "finance": "Invoices, receipts, payments, expenses, accounting, accounts payable.",
    "procurement": "Purchase orders, vendors, purchasing, sourcing, procurement.",
    "legal": "Contracts, agreements, legal notices, legal documents.",
    "hr": "Resumes, candidates, employees, hiring, recruiting, HR documents.",
    "operations": "Operational reports, forms, procedures, and workflows.",
    "security": "Security-sensitive or security-related documents.",
    "general": "General business documents that do not clearly belong elsewhere.",
}

DOCUMENT_COMPLETENESS_LEVELS = [
    "incomplete",
    "partially_complete",
    "complete",
]

AUTOMATION_READINESS_LEVELS = [
    "not_ready",
    "partially_ready",
    "ready",
]

PROFILE_COMPLETENESS_LEVELS = [
    "incomplete",
    "partially_complete",
    "complete",
]

CORE_QUESTIONS = {
    "document_type": Choice(
        instructions="What type of document is this?",
        criteria=DOCUMENT_TYPES,
    ),
    "department": Choice(
        instructions="Which department should primarily handle this document?",
        criteria=DEPARTMENTS,
    ),
    "is_business_document": Noul(
        instructions="Is this a business-related document?",
    ),
    "is_financial_document": Noul(
        instructions=(
            "Does this document primarily relate to money, payment, purchasing, "
            "expenses, accounting, or financial processing?"
        ),
    ),
    "requires_human_review": Noul(
        instructions=(
            "Does the available evidence contain enough uncertainty, ambiguity, "
            "missing information, or sensitivity that a human should review it "
            "before automated processing?"
        ),
    ),
    "document_completeness": Score(
        instructions=(
            "How complete is this document for its apparent document type, based "
            "only on the supplied evidence? Consider whether the expected core "
            "information for that type is present and usable."
        ),
        criteria=DOCUMENT_COMPLETENESS_LEVELS,
    ),
}

FINANCE_QUESTIONS = {
    "has_purchase_order": Noul(
        instructions=(
            "Does the supplied document explicitly contain a purchase-order number "
            "or purchase-order reference? Use evidence.purchase_order_reference_detected "
            "and evidence.purchase_order_references as direct supporting evidence when present."
        ),
    ),
    "contains_payment_information": Noul(
        instructions=(
            "Does the document contain information intended to facilitate or request "
            "payment, such as amount due, payment instructions, bank details, cash, or change?"
        ),
    ),
    "has_line_items": Noul(
        instructions=(
            "Does the document contain identifiable purchased items, products, or services "
            "with quantities, prices, or amounts?"
        ),
    ),
    "needs_po_review": Noul(
        instructions=(
            "For a finance or procurement workflow, does the document appear to need human "
            "review because of purchase-order uncertainty or because a purchase-order reference "
            "is absent where it would be useful? Use the supplied purchase-order evidence."
        ),
    ),
    "automation_readiness": Score(
        instructions=(
            "How ready is this financial document for automated processing based on clarity, "
            "completeness, and the presence of useful transaction evidence?"
        ),
        criteria=AUTOMATION_READINESS_LEVELS,
    ),
}

HR_QUESTIONS = {
    "is_resume": Noul(
        instructions="Is the supplied document a person's resume or CV?",
    ),
    "has_experience": Noul(
        instructions=(
            "Does the document contain identifiable work experience "
            "or employment history?"
        ),
    ),
    "has_education": Noul(
        instructions=(
            "Does the document contain identifiable education "
            "or academic background?"
        ),
    ),
    "has_skills": Noul(
        instructions=(
            "Does the document contain an Artificial Intelligence, "
            "computer science, or related skills sections?"
        ),
    ),
    "profile_completeness": Score(
        instructions=(
            "How complete is the candidate profile for Artificial Intelligence, computer science, or related roles based on the supplied evidence?s"
        ),
        criteria=PROFILE_COMPLETENESS_LEVELS,
    ),
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _serialize_choice(answer: Any) -> dict[str, Any]:
    probabilities = getattr(answer, "probabilities", {}) or {}
    return {
        "value": getattr(answer, "choice", None),
        "confidence": _safe_float(getattr(answer, "confidence", 0.0)),
        "probabilities": {
            str(key): _safe_float(value)
            for key, value in probabilities.items()
        },
    }


def _serialize_noul(answer: Any) -> dict[str, Any]:
    return {
        "probability": _safe_float(getattr(answer, "noul", 0.0)),
    }


def _serialize_score(answer: Any, levels: list[str]) -> dict[str, Any]:
    probabilities = getattr(answer, "probabilities", {}) or {}
    legend = getattr(answer, "legend", {}) or {}
    score = _safe_float(getattr(answer, "score", 0.0))

    # Jev's Score is continuous across ordered levels. For the dashboard we
    # also expose a normalized 0-1 representation so users don't have to
    # interpret raw values such as 1.26.
    max_score = max(len(levels) - 1, 1)
    normalized = min(max(score / max_score, 0.0), 1.0)

    return {
        "score": score,
        "normalized_score": normalized,
        "confidence": _safe_float(getattr(answer, "confidence", 0.0)),
        "levels": levels,
        "probabilities": {
            str(key): _safe_float(value)
            for key, value in probabilities.items()
        },
        "legend": {
            str(key): str(value)
            for key, value in legend.items()
        },
    }


def _serialize_response(
    response: Any,
    score_levels: dict[str, list[str]],
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "choices": {},
        "nouls": {},
        "scores": {},
    }

    for key, answer in (getattr(response, "choices", {}) or {}).items():
        result["choices"][key] = _serialize_choice(answer)

    for key, answer in (getattr(response, "nouls", {}) or {}).items():
        result["nouls"][key] = _serialize_noul(answer)

    for key, answer in (getattr(response, "scores", {}) or {}).items():
        result["scores"][key] = _serialize_score(
            answer,
            score_levels.get(key, ["low", "medium", "high"]),
        )

    return result


def _extract_document_evidence(document_text: str) -> dict[str, Any]:
    """Extract small deterministic facts before asking Jev to interpret them."""
    upper_text = document_text.upper()

    po_patterns = [
        r"\bP\.\s*O\.\s*(?:NUMBER|NO\.?|#)?\s*[:#-]?\s*([A-Z0-9]+(?:[-/][A-Z0-9]+)+)\b",
        r"\bPURCHASE\s+ORDER\s*(?:NUMBER|NO\.?|#)?\s*[:#-]?\s*([A-Z0-9]+(?:[-/][A-Z0-9]+)+)\b",
    ]
    po_references: list[str] = []
    for pattern in po_patterns:
        for match in re.finditer(pattern, upper_text):
            value = match.group(1).strip()
            if value not in po_references:
                po_references.append(value)

    total_patterns = [
    r"\bTOTAL\s+DUE\b\s*[:#-]?\s*(?:USD\s*)?([$€£₹]?\s?[\d,]+(?:\.\d{2})?)",
    r"\bAMOUNT\s+DUE\b\s*[:#-]?\s*(?:USD\s*)?([$€£₹]?\s?[\d,]+(?:\.\d{2})?)",
    r"\bGRAND\s+TOTAL\b\s*[:#-]?\s*(?:USD\s*)?([$€£₹]?\s?[\d,]+(?:\.\d{2})?)",
    r"\bTOTAL\s+AMOUNT\b\s*[:#-]?\s*(?:USD\s*)?([$€£₹]?\s?[\d,]+(?:\.\d{2})?)",
   ]
    total_amount: float | None = None
    total_currency = None
    for pattern in total_patterns:
        match = re.search(pattern, upper_text)
        if not match:
            continue
        raw = match.group(1).replace(",", "").strip()
        symbol = raw[:1] if raw[:1] in "$€£₹" else None
        number = raw[1:].strip() if symbol else raw
        try:
            total_amount = float(number)
            total_currency = symbol
            break
        except ValueError:
            continue

    experience_matches = re.findall(
        r"\b(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b",
        upper_text,
    )
    experience_summary = None
    if experience_matches:
        years = [float(value) for value in experience_matches]
        max_years = max(years)
        if max_years.is_integer():
            experience_summary = f"{int(max_years)}+ years"
        else:
            experience_summary = f"{max_years:g}+ years"

    return {
        "purchase_order_reference_detected": bool(po_references),
        "purchase_order_references": po_references[:10],
        "total_amount": total_amount,
        "total_currency": total_currency,
        "experience_summary": experience_summary,
    }


def _run_questions(
    state: dict[str, Any],
    questions: dict[str, Any],
    score_levels: dict[str, list[str]],
) -> dict[str, Any]:
    logger.debug("Running Jev evaluation with %d questions", len(questions))
    with TypeSafeClient() as client:
        response = client.system_one(
            state=state,
            questions=questions,
        )
    return _serialize_response(response, score_levels)


def evaluate_document(document_text: str) -> dict[str, Any]:
    """Evaluate one document with Jev's Choice, Noul, and Score primitives."""
    logger.info("Starting Jev evaluation on document snippet length=%d", len(document_text))
    evidence = _extract_document_evidence(document_text)
    state = {
        "document": document_text,
        "evidence": evidence,
    }

    try:
        core = _run_questions(
            state,
            CORE_QUESTIONS,
            {
                "document_completeness": DOCUMENT_COMPLETENESS_LEVELS,
            },
        )

        detected_type = core["choices"]["document_type"]["value"]
        detected_department = core["choices"]["department"]["value"]
        logger.info(
            "Core classification: type=%s department=%s",
            detected_type,
            detected_department,
        )

        if detected_type in {"invoice", "receipt", "purchase_order"} or detected_department in {
            "finance",
            "procurement",
        }:
            domain = "finance"
            domain_questions = FINANCE_QUESTIONS
            domain_score_levels = {
                "automation_readiness": AUTOMATION_READINESS_LEVELS,
            }
        elif detected_type == "resume" or detected_department == "hr":
            domain = "hr"
            domain_questions = HR_QUESTIONS
            domain_score_levels = {
                "profile_completeness": PROFILE_COMPLETENESS_LEVELS,
            }
        else:
            domain = "general"
            domain_questions = {}
            domain_score_levels = {}

        if domain_questions:
            domain_result = _run_questions(
                {
                    **state,
                    "core_jev_decisions": core,
                    "detected_domain": domain,
                },
                domain_questions,
                domain_score_levels,
            )
        else:
            domain_result = {"choices": {}, "nouls": {}, "scores": {}}

        result = {
            "core": core,
            "domain": domain,
            "domain_decisions": domain_result,
            "evidence": evidence,
        }
        logger.info("Completed Jev evaluation for domain=%s", domain)
        return result
    except Exception:
        logger.exception("Jev evaluation failed for document snippet length=%d", len(document_text))
        raise
