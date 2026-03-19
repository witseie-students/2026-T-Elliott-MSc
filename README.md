# 2026-T-Elliott-MSc-Dissertation – *Addressing Biomedical Literature Overload through Knowledge Graph Generation and Agentic Reasoning*

## Authors
**Student:** Taine J. Elliott
**Supervisor:** Dr. Martin Bekker
**Co-Supervisors:** Dr. Stephen Levitt, Dr. Ken Nixon


## Abstract

*Biomedical literature is growing at an unprecedented rate. As a result, researchers are likely to struggle keeping up with the growing volume. Current biomedical literature search tools retrieve large volumes of results, but lack the ability to deliver precise, context-aware answers. This work extends and contributes to research in information extraction for knowledge graph generation and knowledge graph retrieval augmented generation (graphRAG), with the goal of connecting all biomedical literature through units of knowledge. The work documents how a knowledge graph of propositions is built using 350 biomedical abstracts from the PubMedQA dataset. During construction, a back-translation methodology for validation was pioneered. Once constructed, questions derived from the dataset were answered using the knowledge graph with both single-iteration and recursive retrieval approaches. The system's performance was compared to a baseline (where the latter had access to the full context prior to graph generation). Through back-translation, the average cosine similarity between the reconstructed abstracts of propositions and the original abstracts was 0.913. The cosine similarity distribution was calibrated against the Semantic Textual Similarity Benchmark (STS-B), showing that reconstructed abstracts were completely equivalent to the original texts. Answers derived from the knowledge graph achieved 93.03\% of the baseline F1 score with single-iteration retrieval, and 86.07\% with recursive retrieval. This performance implies that knowledge graphs are capable of storing biomedical knowledge faithfully, and that they enable precise retrieval for effective reasoning. Ultimately, this dissertation demonstrates that biomedical literature can be captured in knowledge graph form, can effectively be reasoned with, signalling how researchers might better navigate vast quantities of biomedical knowledge.*

📄 **Full dissertation PDF**: [paper/Taine_Elliott_MSc_Dissertation.pdf](paper/Taine_Elliott_MSc_Dissertation.pdf)

---
## Table of Contents
1. [Project Overview](#project-overview)
2. [Repository Layout](#repository-layout)
3. [Quick Start](#quick-start)
4. [Backend (set-up & usage)](#backend)
5. [Frontend (set-up & usage)](#frontend)
6. [Datasets](#datasets)
7. [Environment Variables (.env)](#environment-variables-env)
8. [Conda Environment](#conda-environment)

---
## Project Overview
This dissertation demonstrates how a domain‑specific **knowledge‑graph** can improve question‑answering performance when paired with **Retrieval‑Augmented Generation (RAG)**.  Two Django apps map directly to the experimental chapters:
<p align="center">
  <img src="paper/system_architecture.png" alt="System architecture diagram" width="70%">
</p>

| Chapter | Django App | Purpose |
|---------|------------|---------|
| 3 | `knowledge-graph-generator` | Parse PubMed abstracts, extract biomedical triples, and populate a Neo4j graph. |
| 4 | `graphRAG` | Expose graph‑aware retrieval endpoints consumed by the React frontend and evaluate QA metrics. |

---
## Repository Layout
```
└── 2026-T-Elliott-MSc/
    ├── backend/                  # Django project
    │   ├── knowledge-graph-generator/
    │   └── graphRAG/
    ├── frontend/                 # React (Vite) SPA
    ├── data/                     # Raw & processed datasets
    │   ├── pubmedqa_train.jsonl
    │   └── pubmed_stats.csv
    ├── environment.yml           # Conda spec (see below)
    ├── .env.example              # Template for secrets & config
    └── README.md                 # You are here
```

---
## Quick Start
```bash
# 1. clone the repo
git clone https://github.com/witseie-students/2026-T-Elliott-MSc.git
cd 2026-T-Elliott-MSc

# 2. create the Conda environment (Python 3.11)
conda env create -f environment.yml
conda activate msc

# 3. copy & edit environment variables
cp .env.example .env
open -e .env   # edit secrets / keys

# 4. apply migrations & run the API
cd backend
python manage.py migrate
python manage.py runserver 0.0.0.0:8000

# 5. in a new terminal tab, start the React dev server
cd ../frontend
npm install
npm run dev      # http://localhost:5173
```

---
## Backend
### Key Dependencies
* Django 5.x
* Django REST Framework
* Neo4j-Driver & Neomodel
* SpaCy + ScispaCy models
* NetworkX, RDFlib
* LangChain / OpenAI SDK (for RAG evaluation)

### Running migrations & seed jobs
```bash
# inside backend/
python manage.py migrate          # create tables
python manage.py ingest_pubmed    # custom command – builds the graph
```

### API Endpoints (high-level)
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/docs/<pmid>/triples/` | Extracted triples for a single PubMed article |
| `POST` | `/api/v1/rag/query/` | RAG query with graph-aware retrieval |

Full OpenAPI docs are auto-generated at `/api/schema/`.

---
## Frontend
* React 18 + Vite + TypeScript
* Chakra UI (component library)
* Axios (API client)
* React Router

```bash
# development hot-reload
npm run dev

# production build
npm run build && npm run preview
```

The app is pre-configured to proxy `/api/*` to `localhost:8000` in development.

---
## Datasets
* **PubMedQA** – question-answer pairs with ground‑truth labels.
* **PubMed Statistics** – CSV containing yearly publication counts used for exploratory analysis (Chapter 2).

Raw files live under `data/`; processed artefacts are cached in the Django media folder (`backend/media/`).

---
## Environment Variables (.env)
Below is a minimal template; copy it to `.env` and fill in the blanks.

```env
# Django
DJANGO_SECRET_KEY=CHANGEME
DJANGO_DEBUG=True
ALLOWED_HOSTS=127.0.0.1,localhost

# Database
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=CHANGEME

# OpenAI / HuggingFace
OPENAI_API_KEY=
HF_TOKEN=
```

> **Note:** If you prefer, you can also pin library versions here, e.g. `DJANGO_VERSION=5.0.2`, but the canonical list lives in `environment.yml`.

---
## Conda Environment
An exhaustive, reproducible spec is stored in **`environment.yml`**.  Excerpt:
```yaml
name: msc
channels:
  - conda-forge
  - defaults
dependencies:
  - python=3.11
  - django>=5,<6
  - djangorestframework
  - neo4j=5.*
  - networkx
  - spacy
  - scispacy
  - langchain
  - openai
  - nodejs  # required to build frontend
  - pip
  - pip:
      - rdflib
```
Regenerate with:
```bash
conda env export --no-builds > environment.yml
```




