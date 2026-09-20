# Universal Document Decision Engine

A small proof-of-concept for turning documents into **typed AI decisions** instead of relying on generated text.

Built with:

- **Docling** — document parsing and structured evidence
- **Jev by TypeSafe AI** — typed decisions using **Choice, Noul, and Score**
- **Python** — deterministic business rules and routing
- **FastAPI** — backend API
- **Streamlit** — interactive demo UI

## Demo

A short walkthrough of the Document Decision Engine is included here:

**[Watch the demo video](./docs/demo.mp4)**

> Add the demo video to the repository at `docs/demo.mp4`.

## What it does

The system first determines what kind of document it is and which business area should handle it.

It then asks document-specific questions using Jev.

### Resumes

For resumes, Jev evaluates questions such as:

- Is this a resume?
- Does it contain work experience?
- Does it contain education?
- Does it contain skills?
- How complete is the candidate profile?

### Finance documents

For invoices and receipts, Jev evaluates questions such as:

- Is there a purchase order?
- Is there an invoice number?
- Is vendor information present?
- Are payment terms present?
- Is tax information present?
- Are line items present?
- Is a total amount present?
- What is the payment status?
- Does the document need PO review?
- Is the document ready for automated processing?

The exact values that can be deterministically extracted from the document are kept separate from Jev's semantic decisions.

## Architecture

```text
Document
   |
   v
Docling
   |
   +--> Structured Evidence
   |
   v
Jev
   |
   +-----------------------------+
   |             |               |
 Choice         Noul            Score
   |             |               |
 What is it?   Does it have?   How complete?
 Who handles?  Does it need?   How ready?
   |             |               |
   +-------------+---------------+
                 |
                 v
          Python Business Rules
                 |
                 v
        Auto Process / Human Review
```

The separation is intentional:

**Docling extracts. Jev decides. Python executes.**

## Jev in this project

The project uses Jev's three typed decision primitives:

### Choice

Used when the system needs to select one option.

Examples:

- Document type → invoice / receipt / resume / ...
- Department → finance / HR / procurement / ...
- Payment status → payment requested / payment completed / ...

### Noul

Used for yes/no-style decisions represented as probabilities.

Examples:

- Has purchase order?
- Has invoice number?
- Has experience?
- Has skills?
- Needs PO review?
- Has required invoice fields?

### Score

Used for ordered assessments.

Examples:

- Document completeness
- Automation readiness
- Candidate profile completeness

This allows the application to consume structured decisions directly rather than parsing generated prose.

## Supported document examples

The current POC has been tested with:

- Invoices
- Receipts
- Resumes

The document pipeline accepts:

- PDF
- PNG
- JPG / JPEG
- WEBP
- TIFF

## Tech stack

| Component | Purpose |
|---|---|
| Python | Core application logic |
| Docling | Document parsing and evidence |
| Jev / TypeSafe AI | Typed AI decisions |
| FastAPI | Backend API |
| Streamlit | Demo interface |
| Pydantic | API schemas |
| Uvicorn | ASGI server |

## Project structure

```text
Universal-Document-Decision-Engine/
|
├── app/
│   ├── docling_parser.py    # Document parsing + structured evidence
│   ├── jev.py               # Jev Choice / Noul / Score definitions
│   ├── router.py             # Deterministic business routing
│   ├── schemas.py            # Pydantic response models
│   └── main.py               # FastAPI application
|
├── frontend/
│   └── streamlit_app.py     # Streamlit UI
|
├── data/
│   ├── invoice-0-4.pdf
│   ├── invoice v2.png
│   ├── recieptt.jpg
│   ├── resume_1.pdf
│   └── resume_2.pdf
|
├── docs/
│   └── demo.mp4             # Add the demo video here
|
├── .env.example
├── .gitignore
└── README.md
```

## Getting started

### 1. Clone the repository

```bash
git clone https://github.com/Navanit-git/Universal-Document-Decision-Engine.git
cd Universal-Document-Decision-Engine
```

### 2. Create a virtual environment

```bash
python3.12 -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure the Jev API key

Create a `.env` file:

```env
TYPESAFE_API_KEY=your_actual_typesafe_api_key
```

Do not commit the `.env` file.

### 5. Start the FastAPI backend

```bash
uvicorn app.main:app --reload
```

The API will be available at:

```text
http://127.0.0.1:8000
```

### 6. Start Streamlit

In another terminal:

```bash
streamlit run frontend/streamlit_app.py
```

Then open the Streamlit URL shown in the terminal.

## API

### Health check

```http
GET /health
```

### Analyze a document

```http
POST /analyze
```

Upload a supported document as the `file` form field.

The response contains:

- Document classification
- Department classification
- Jev Choice decisions
- Jev Noul probabilities
- Jev Score results
- Extracted evidence
- Final application action

## Design principle

The goal of this project is not to replace every piece of application logic with an LLM.

Instead, it explores a more explicit pattern:

```text
Document
   ↓
Evidence
   ↓
Typed AI decisions
   ↓
Deterministic application logic
   ↓
Action
```

This makes the AI output easier for the surrounding software to consume, inspect, and route.

## Status

This is a **proof-of-concept / experimental project**, not a production document-processing system.

The current implementation focuses on demonstrating the interaction between **Docling, Jev, and deterministic Python business logic** across a small set of document types.

## License

Add a license here if you decide to open-source the project under a specific license.
