<div align="center">

# 🧭 LegalCompass

**Understand your rights. Know your next step.**

A multilingual legal information tool for employment and labour issues in India.
Describe your problem in your own language and get the relevant law, the right authority to approach, and a draft notice.

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![Flask](https://img.shields.io/badge/Backend-Flask-black)
![LangGraph](https://img.shields.io/badge/Orchestration-LangGraph-green)
![LangChain](https://img.shields.io/badge/Framework-LangChain-blue)
![Gemini](https://img.shields.io/badge/LLM-Google%20Gemini-purple)
![RAG](https://img.shields.io/badge/AI-RAG-orange)
![ChromaDB](https://img.shields.io/badge/Vector%20DB-ChromaDB-red)
![MiniLM](https://img.shields.io/badge/Embeddings-MiniLM-yellow)
![Sarvam AI](https://img.shields.io/badge/Translation-Sarvam%20AI-blueviolet)
![PyMuPDF](https://img.shields.io/badge/PDF-PyMuPDF-darkgreen)
![Vanilla JS](https://img.shields.io/badge/Frontend-Vanilla%20JS-yellow)
![License](https://img.shields.io/badge/License-MIT-yellow)
![Status](https://img.shields.io/badge/Version-V1-orange)

</div>

---
## Table of Contents

- [About](#about)
- [The Problem](#the-problem)
- [Features](#features)
- [How It Works](#how-it-works)
- [User Workflow](#user-workflow)
- [Architecture](#architecture)
- [RAG Architecture](#rag-architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Supported Languages](#supported-languages)
- [Design Principles](#design-principles)
- [Known Limitations](#known-limitations)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [Disclaimer](#disclaimer)
- [License](#license)
- [Author](#author)

---

## About

LegalCompass is a multilingual legal information platform designed to help people understand employment and labour laws in India. It brings legal information, relevant provisions, practical guidance, government authority information, and document drafting into one simple interface.

### V1 Scope

LegalCompass V1 focuses on employment and labour-related matters, including salary and wage issues, workplace disputes, termination-related situations, provident fund, gratuity, maternity-related matters, and access to legal aid.

The system does not claim to cover every legal issue or provide a complete legal remedy for every case.

## The Problem

Most workers do not know which law protects them, what remedy they have, or which office to approach. Getting this information usually means paying for a lawyer or visiting crowded legal aid offices. 

-- LegalCompass gives a first, grounded answer in a few seconds, so the worker knows where to start.

## Features

- **Write in your language.** Input in English or any supported Indian language. Language is detected automatically.
- **Grounded legal answer.** Answers come from retrieved text of official labour laws, not from model memory.
- **Plain-language explanation.** Each relevant provision is explained in simple words, with section number and page.
- **Applied to your case.** A short explanation of how the law applies to the facts you gave.
- **Honest gaps.** The app lists what it could not confirm (for example, missing facts or unclear jurisdiction).
- **Next steps.** A short, ordered list of practical actions.
- **Right authority.** Picks the relevant labour office (state or central) with address, phone, website and map link. Shows a confidence level and a verification note.
- **Draft notice.** Generates a deterministic, editable legal notice or complaint draft using the facts available from the case. Missing facts are omitted rather than invented.
- **Translate button.** Translates the full result into the user's language, and back to English.
- **Legal sources.** Shows the exact retrieved law text. Only relevant sources are shown.
- **Follow-up questions.** If key facts are missing, the app asks a few short questions before answering.

---

## User Workflow

```text
┌───────────────────────────────┐
│        Describe Problem       │
│ English / Indian Language     │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│       Language Detection      │
│ Detect → Translate if needed  │
└───────────────┬───────────────┘
                │
                ▼
        ┌─────────────────┐
        │ Key facts       │
        │ available?      │
        └───────┬─────┬───┘
                │ Yes │ No
                │     ▼
                │  ┌──────────────────────┐
                │  │ Follow-up Questions  │
                │  │ Answer / Skip        │
                │  └──────────┬───────────┘
                │             │
                └──────┬──────┘
                       ▼
┌────────────────────────────────────────┐
│              Case Analysis             │
│ Facts → Legal Retrieval → Evidence     │
│ → Reasoning → Authority → Draft        │
└────────────────────┬───────────────────┘
                     │
                     ▼
┌────────────────────────────────────────┐
│              Result Cards              │
│                                        │
│  Case Summary                          │
│        ↓                               │
│  What the Law Says                     │
│        ↓                               │
│  How This Applies to You               │
│        ↓                               │
│  What You Can Do                       │
│        ↓                               │
│  Relevant Authority                    │
│        ↓                               │
│  Draft Notice                          │
│        ↓                               │
│  Legal Sources                         │
└────────────────────┬───────────────────┘
                     │
          ┌──────────┴──────────┐
          ▼                     ▼
┌──────────────────┐   ┌──────────────────┐
│ Translate Result │   │ Copy / Edit Draft│
│ Optional         │   │ Review facts     │
└────────┬─────────┘   └────────┬─────────┘
         │                      │
         └──────────┬───────────┘
                    ▼
          ┌──────────────────────┐
          │     Take Action      │
          │ Documents + Authority│
          │ / DLSA Legal Help    │
          └──────────────────────┘
```

---

## Architecture

```
USER INPUT (any Indian language)
         │
         ▼
  [Input Processor]      — sanitise, normalise
         │
         ▼
  [Language Service]     — detect language, translate → English (Sarvam AI)
         │
         ▼
  [Intent Analyzer]      — Gemini structured extraction → CaseAnalysis
         │
         ▼
  [Context Manager]      — identify missing facts → clarifying questions
         │
    ┌────┴────────────────────┐
    │ needs_context?          │
    ▼ YES                     ▼ NO
[Ask User]           [Legal Retriever]  ← multi-query ChromaDB retrieval
                             │
                             ▼
                    [Evidence Selector] ← Gemini classifies: DIRECT/SUPPORTING/IRRELEVANT
                             │
                             ▼
                    [Legal Reasoner]    ← Gemini explains retrieved evidence (NOT inventing law)
                             │
                             ▼
                    [Authority Mapper]  ← deterministic JSON lookup (no AI)
                             │
                             ▼
                    [Action Recommender] ← evidence-grounded next steps
                             │
                             ▼
                    [Document Drafter]  ← template engine, no fabrication
                             │
                             ▼
                    [Response Builder]  ← clean API response
                             │
                             ▼
                    [Translation]       ← English → user's language (Sarvam AI)
                             │
                             ▼
                         [FLASK UI]
```

---

## RAG Architecture

```
PDF Documents
      │
      ▼
[PDF Extraction]    — PyMuPDF, page-annotated ([PAGE:N] markers)
      │
      ▼
[Section Chunking]  — section-aware, not N-character splits
      │              preserves: section number, title, subsections, page
      ▼
[Filtering]         — removes TOC, page numbers, empty sections, heading-only chunks
      │
      ▼
[MiniLM Embedding]  — sentence-transformers/all-MiniLM-L6-v2 (local, free)
      │
      ▼
[ChromaDB]          — collection: legal_corpus_v1 (cosine similarity)
      │
      ▼
[Multi-Query Retrieval] — 6+ focused queries per case (substantive + procedural + remedy + enforcement)
      │
      ▼
[Legal Reranker]    — semantic similarity + legal concept match + document preference + provision type
      │
      ▼
[Deduplication]     — no duplicate sections
      │
      ▼
[Evidence Selection] — Gemini classifies candidates: DIRECT / SUPPORTING / COMPLEMENTARY / IRRELEVANT
```
---

## Project Structure

```
LegalCompass/
├── app/
│   ├── main.py                    Flask entry point
│   ├── routes/api.py              API routes
│   ├── templates/index.html       Frontend
│   └── static/
│       ├── css/style.css
│       └── js/app.js
│
├── agent/
│   ├── graph.py                   LangGraph pipeline
│   ├── state.py                   State models (TypedDict + Pydantic)
│   ├── nodes/
│   │   ├── input_processor.py
│   │   ├── language_service.py
│   │   ├── intent_analyzer.py
│   │   ├── context_manager.py
│   │   ├── legal_retriever.py
│   │   ├── evidence_selector.py
│   │   ├── legal_reasoner.py
│   │   ├── authority_mapper.py
│   │   ├── action_recommender.py
│   │   ├── document_drafter.py
│   │   └── response_builder.py
│   └── services/
│       ├── language_service.py    Sarvam AI integration
│       ├── authority_service.py   Deterministic authority matching
│       └── drafting_templates.py  Document templates
│
├── rag/
│   ├── ingest.py                  PDF → ChromaDB ingestion pipeline
│   ├── chunker.py                 Section-aware chunking
│   ├── embed.py                   MiniLM embeddings
│   ├── vector_store.py            ChromaDB wrapper
│   ├── retriever.py               Multi-query retrieval
│   └── legal_ranker.py            Legal reranking + deduplication
│
├── data/
│   ├── authorities/
│   │   └── labour_authorities.json
│   └── legal_corpus/
│       ├── raw/                   Source PDFs (12 documents)
│       ├── processed/             Extracted text
│       └── registry/
│           └── corpus_registry.json
│
├── tests/
│   ├── test_retrieval.py
│   └── test_end_to_end.py
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```


## Technology Stack

| Component | Technology | Why |
|-----------|-----------|-----|
| Backend | Flask | Lightweight, simple |
| Orchestration | LangGraph | Graph-based pipeline with state |
| LLM | Gemini 1.5 Flash (Google) | Structured output, low cost |
| Translation | Sarvam AI | Indian language specialist |
| Embeddings | MiniLM L6 v2 | Local, free, fast |
| Vector DB | ChromaDB | Local, persistent, no server needed |
| PDF parsing | PyMuPDF | Fast, accurate |
| Frontend | Vanilla HTML / CSS / JS | No framework overhead |
| State | Pydantic v2 | Strict type enforcement |


```
---

## Getting Started

### Prerequisites

- Python 3.10 or higher
- A Google Gemini API key
- A Sarvam AI API key (needed for language detection and translation)

### Installation

```bash
# 1. Clone the repo
git clone https://github.com/<Aqifcodes>/LegalCompass.git
cd LegalCompass

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file (see Configuration below)
```
> The legal corpus must be ingested before first use. Run your ingestion script once, then start the app.

### Run

```bash
python -m app.main
```

Open [http://localhost:5000](http://localhost:5000).

## Configuration

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_gemini_key
SARVAM_API_KEY=your_sarvam_key
```

## API Endpoints

| Method | Route | Purpose |
|--------|-------|---------|
| GET | `/` | Frontend page |
| GET | `/api/status` | Health check, shows whether Gemini and Sarvam keys are set |
| POST | `/api/analyze` | Main analysis. Returns the result or follow-up questions |
| POST | `/api/context` | Resume the analysis after the user answers follow-up questions |
| POST | `/api/draft` | Generate a draft document separately |
| POST | `/api/translate` | Translate a finished result into the user's language |

Example request:

```json
POST /api/analyze
{
  "message": "My employer has not paid my salary for three months.",
  "language": "auto",
  "draft_requested": true
}
```

## Supported Languages

English, Hindi, Telugu, Tamil, Kannada, Malayalam, Marathi, Bengali, Gujarati, Punjabi, Odia, Assamese.

## Design Principles

> **The LLM is not the source of law. The database is.**

- **Grounded, not guessed.** Legal explanations are based on retrieved evidence from the curated legal corpus.
- **No invented facts.** No made-up deadlines, penalties or court threats. Unknown details stay as placeholders.
- **Rule-based authority mapping.** The authority is chosen by fixed rules, not by the LLM.
- **Say what is unknown.** Gaps and uncertainties are shown to the user.
- **Original law text stays original.** Legal Sources are shown as retrieved, in English.
- **Transparent uncertainty.** When the available evidence is insufficient, LegalCompass reports the limitation instead of presenting an unsupported answer.
- **Deterministic drafting.** Draft notices are generated from known case facts and retrieved legal evidence rather than free-form legal invention.
- **Light to run.** Works on a normal laptop without a GPU.


## Known Limitations

- V1 covers employment and labour law only.
- The quality of the legal answer depends on the laws, rules, FAQs and government sources currently included in the LegalCompass corpus.
- Machine-translated drafts can have wording errors, especially in formal letter terms. Review before use.
- Authority details (address, phone) are stored data and may change. Always verify before visiting.
- Jurisdiction (state or central) can depend on facts the user did not give. The app flags this.
- The answer quality depends on the retrieved sources. Some irrelevant sources can still appear in rare cases.



## Roadmap

The following are future directions and are not part of the current V1 implementation.

### Legal Coverage

- V2 — Consumer law
- V3 — Cyber law
- V4 — Family and personal legal issues
- V5 — Broader legal domains

### Product Improvements

- Expanded and continuously maintained legal corpus
- Improved retrieval and filtering of relevant provisions
- More comprehensive authority coverage
- Additional tested employment-law scenarios
- Native draft templates for selected Indian languages
- Optional translation of selected legal-source explanations


## Disclaimer

LegalCompass provides legal **information**, not legal advice. It is not a substitute for a qualified lawyer. Verify facts, procedures and current requirements before taking any legal action. For free legal help, contact your District Legal Services Authority (DLSA) or visit [nalsa.gov.in](https://nalsa.gov.in).



## License

This project is open source under the [MIT License](LICENSE).

## Author

**Aqif**
B.Tech CSE (AI & ML)

---

<div align="center">

**Built with ❤️ for India's workers**

*Know your rights. Know your next step.*

</div>

---
