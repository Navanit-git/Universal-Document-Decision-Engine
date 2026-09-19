from __future__ import annotations

import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Jev Document Decision Engine",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .block-container {
        max-width: 1400px;
        padding-top: 1.25rem;
        padding-bottom: 1.5rem;
    }

    .decision-value {
        font-size: 1.05rem;
        font-weight: 700;
        line-height: 1.2;
        margin-bottom: 0.45rem;
    }

    .score-value {
        font-size: 1.55rem;
        font-weight: 750;
        line-height: 1.15;
        margin: 0.1rem 0 0.2rem 0;
    }

    .fact-label {
        color: #6b7280;
        font-size: 0.82rem;
        margin-bottom: 0.15rem;
    }

    .fact-value {
        font-size: 1.15rem;
        font-weight: 700;
    }

    div[data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 10px;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.4rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Jev Document Decision Engine")
st.caption("Docling → evidence → Jev Choice + Noul + Score")

uploaded_file = st.file_uploader(
    "Upload a PDF or document image",
    type=["pdf", "png", "jpg", "jpeg", "webp", "tif", "tiff"],
)


def pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def titleize(key: str) -> str:
    return key.replace("_", " ").title()


def render_choice(label: str, data: dict) -> None:
    value = data.get("value", "-") or "-"
    confidence = float(data.get("confidence", 0.0))

    with st.container(border=True):
        st.caption(label)
        st.markdown(f'<div class="decision-value">{value.replace("_", " ").title()}</div>', unsafe_allow_html=True)
        st.caption(f"Confidence {pct(confidence)}")


def render_noul(label: str, data: dict) -> None:
    probability = float(data.get("probability", 0.0))

    with st.container(border=True):
        st.caption(label)
        st.progress(
            min(max(probability, 0.0), 1.0),
            text=pct(probability),
        )


def render_score(label: str, data: dict) -> None:
    normalized = float(data.get("normalized_score", 0.0))
    raw_score = float(data.get("score", 0.0))
    confidence = float(data.get("confidence", 0.0))

    with st.container(border=True):
        st.caption(label)
        st.markdown(
            f'<div class="score-value">{pct(normalized)}</div>',
            unsafe_allow_html=True,
        )
        st.progress(
            min(max(normalized, 0.0), 1.0),
            text=pct(normalized),
        )
        st.caption(f"Confidence {pct(confidence)}")
        with st.expander("Details", expanded=False):
            st.caption(f"Jev raw score: {raw_score:.2f}")
            st.json(data.get("probabilities", {}))


def render_column_grid(items: dict, renderer) -> None:
    if not items:
        st.caption("No decisions for this document type.")
        return

    for index, (key, data) in enumerate(items.items()):
        renderer(titleize(key), data)


def first_value(data: dict, key: str, default: str = "-") -> str:
    value = data.get(key)
    return default if value in (None, "") else str(value)


if uploaded_file:
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }

    with st.spinner("Running Docling + Jev..."):
        try:
            response = requests.post(
                f"{API_URL}/analyze",
                files=files,
                timeout=180,
            )
            response.raise_for_status()
            result = response.json()
        except requests.RequestException as exc:
            st.error(f"API error: {exc}")
            st.stop()

    jev = result.get("jev", {})
    core = jev.get("core", {})
    domain = jev.get("domain", "general")
    domain_decisions = jev.get("domain_decisions", {})
    evidence = jev.get("evidence", {})

    all_choices = core.get("choices", {})
    all_nouls = {
    **core.get("nouls", {}),
    **domain_decisions.get("nouls", {}),
}

 
    all_scores = {
        **core.get("scores", {}),
        **domain_decisions.get("scores", {}),
    }

    document_type = first_value(result, "document_type")
    department = first_value(result, "department")
    total_amount = evidence.get("total_amount")
    total_currency = evidence.get("total_currency") or ""
    experience_summary = evidence.get("experience_summary")

    # Resume-specific UI: hide generic routing signals
    if document_type == "resume":
            hidden_resume_nouls = {
                "is_business_document",
                "is_financial_document",
                "requires_human_review",
            }
            all_nouls = {
                key: value
                for key, value in all_nouls.items()
                if key not in hidden_resume_nouls
            }

    # ---------------------------------------------------------
    # Simple business-facing summary
    # ---------------------------------------------------------
    st.subheader("Document summary")
    s1, s2, s3 = st.columns(3)

    s1.metric("Document", document_type.replace("_", " ").title())
    s2.metric("Department", department.title())

    if document_type in {"invoice", "receipt"}:
        payment_status = (
            domain_decisions
            .get("choices", {})
            .get("payment_status", {})
            .get("value", "unknown")
        )

        s3.metric(
            "Payment Status",
            payment_status.replace("_", " ").title(),
        )
    elif document_type == "resume":
        has_experience = (
            domain_decisions
            .get("nouls", {})
            .get("has_experience", {})
            .get("probability", 0.0)
        )

        s3.metric(
            "Has Experience",
            "Yes" if has_experience >= 0.5 else "No",
        )
    else:
        s3.metric("Document Domain", domain.title())

    st.divider()

    # ---------------------------------------------------------
    # All Jev decision types in one screen
    # ---------------------------------------------------------
    st.subheader("Jev Decisions")
    choice_col, noul_col, score_col = st.columns(3, gap="medium")

    with choice_col:
        st.markdown("### Jev — Choice")
        render_column_grid(all_choices, render_choice)

    with noul_col:
        st.markdown("### Jev — Noul")
        render_column_grid(all_nouls, render_noul)

    with score_col:
        st.markdown("### Jev — Score")
        render_column_grid(all_scores, render_score)

    # ---------------------------------------------------------
    # Small, useful extracted facts
    # ---------------------------------------------------------
    if evidence.get("purchase_order_reference_detected") or evidence.get("purchase_order_references"):
        st.divider()
        st.caption("Key extracted fact")
        po_refs = ", ".join(evidence.get("purchase_order_references", [])) or "Detected"
        st.markdown(f"**Purchase Order:** {po_refs}")

    # ---------------------------------------------------------
    # Detailed evidence remains collapsed
    # ---------------------------------------------------------
    with st.expander("Extracted evidence", expanded=False):
        st.code(result.get("extracted_text", ""), language="markdown")

    with st.expander("Raw API response", expanded=False):
        st.json(result)
