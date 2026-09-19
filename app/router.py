from __future__ import annotations

import logging

logger = logging.getLogger("doc_decision.router")

HUMAN_REVIEW_THRESHOLD = 0.65
BUSINESS_DOCUMENT_THRESHOLD = 0.80
LOW_COMPLETENESS_THRESHOLD = 0.50
LOW_READINESS_THRESHOLD = 0.50


def decide_action(jev_result: dict) -> str:
    """Turn Jev's typed judgments into deterministic application routing."""
    core = jev_result.get("core", {})
    choices = core.get("choices", {})
    nouls = core.get("nouls", {})
    scores = core.get("scores", {})

    business_probability = nouls.get("is_business_document", {}).get("probability", 0.0)
    review_probability = nouls.get("requires_human_review", {}).get("probability", 0.0)
    completeness = scores.get("document_completeness", {}).get("normalized_score", 1.0)
    document_type = choices.get("document_type", {}).get("value")

    if review_probability >= HUMAN_REVIEW_THRESHOLD:
        logger.info("Decision route: human_review because review probability %.2f >= %.2f", review_probability, HUMAN_REVIEW_THRESHOLD)
        return "human_review"

    if business_probability < BUSINESS_DOCUMENT_THRESHOLD:
        logger.info("Decision route: human_review because business probability %.2f < %.2f", business_probability, BUSINESS_DOCUMENT_THRESHOLD)
        return "human_review"

    if completeness < LOW_COMPLETENESS_THRESHOLD:
        logger.info("Decision route: human_review because completeness %.2f < %.2f", completeness, LOW_COMPLETENESS_THRESHOLD)
        return "human_review"

    domain = jev_result.get("domain")
    domain_decisions = jev_result.get("domain_decisions", {})

    if domain == "finance":
        finance_nouls = domain_decisions.get("nouls", {})
        finance_scores = domain_decisions.get("scores", {})

        po_review_probability = finance_nouls.get("needs_po_review", {}).get("probability", 0.0)
        readiness = finance_scores.get("automation_readiness", {}).get("normalized_score", 1.0)

        if po_review_probability >= HUMAN_REVIEW_THRESHOLD:
            logger.info("Decision route: human_review because PO review probability %.2f >= %.2f", po_review_probability, HUMAN_REVIEW_THRESHOLD)
            return "human_review"

        if readiness < LOW_READINESS_THRESHOLD:
            logger.info("Decision route: human_review because finance readiness %.2f < %.2f", readiness, LOW_READINESS_THRESHOLD)
            return "human_review"

    elif domain == "hr":
        hr_nouls = domain_decisions.get("nouls", {})
        resume_probability = hr_nouls.get("is_resume", {}).get("probability", 0.0)

        if document_type == "resume" and resume_probability < BUSINESS_DOCUMENT_THRESHOLD:
            logger.info("Decision route: human_review because resume probability %.2f < %.2f", resume_probability, BUSINESS_DOCUMENT_THRESHOLD)
            return "human_review"

    if document_type == "other":
        logger.info("Decision route: human_review because document type is %s", document_type)
        return "human_review"

    logger.info("Decision route: auto_process for document type=%s domain=%s", document_type, domain)
    return "auto_process"
