# Basketball Scouting Platform

A unified multi-page Streamlit application combining all four scouting tools into a single, cohesive platform.

## Pages

| Page | Tool | Description |
|------|------|-------------|
| 1 | 📈 Stock Tracker | Player performance tracking, risers/fallers, trend charts |
| 2 | 🏆 Event Talent Index | Tournament quality scoring with the ETI formula |
| 3 | 📋 AI Report Generator | GPT-4.1-mini scouting reports, DOCX/PDF export |
| 4 | 🤖 Scout Assistant | RAG chatbot with FAISS semantic search |

## Quick Start

```powershell
# From the project root (c:\Users\david\aau_scouting_app)
$env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable('OPENAI_API_KEY','User')

# Copy the workbook into the aau_system folder so all pages auto-load it
Copy-Item AAU_Scouting_System.xlsx aau_system\

# Launch
& "C:\Users\david\AppData\Local\Programs\Python\Python313\python.exe" -m streamlit run aau_system/Home.py --server.port 8505
```

## Project Structure

```
aau_system/
├── Home.py                        # Landing page and navigation hub
├── pages/
│   ├── 1_Stock_Tracker.py
│   ├── 2_Talent_Index.py
│   ├── 3_Report_Generator.py
│   └── 4_Scout_Assistant.py
├── shared/
│   ├── workbook.py                # Unified workbook loader and normalizer
│   ├── filters.py                 # Shared sidebar filter widgets
│   └── secrets.py                 # OpenAI API key resolution
├── modules/
│   ├── stock_tracker/metrics.py   # Stock movement calculations
│   ├── talent_index/event_scoring.py  # ETI formula
│   ├── report_gen/
│   │   ├── prompts.py             # Report mode prompt templates
│   │   └── report_generator.py   # OpenAI report generation + DOCX/PDF
│   └── scout/
│       ├── chatbot.py             # RAG assistant with enhanced query parsing
│       ├── vector_store.py        # FAISS index with hash fallback
│       └── ingest.py              # Document ingestion and cache keying
├── requirements.txt
└── README.md
```

## Data

Place `AAU_Scouting_System.xlsx` in the `aau_system/` folder for automatic loading.
All pages also accept uploads via the sidebar file uploader.

**Workbook schema:**
- Sheet `Player_Evaluations` — per-player per-event rows
- Sheet `Event_Log` — event metadata (name, date range, level)

## AI Features

- **API key:** Set `OPENAI_API_KEY` as an environment variable or add it to `.streamlit/secrets.toml`
- **Report Generator:** Uses `gpt-4.1-mini` via `client.responses.create()`
- **Scout Assistant:** Uses `text-embedding-3-small` for semantic search with a FAISS `IndexFlatIP`; falls back to local hash embeddings when API quota is unavailable
- **Enhanced query parsing:** The chatbot detects age-group terms (15U, 16U, 17U, MS, HS) and role terms (guard, wing, forward, big, center) to pre-filter the DataFrame before retrieval

## ETI Formula

```
ETI = avg_overall/5 * 100 * 0.30
    + avg_upside/5 * 100  * 0.20
    + elite_density        * 0.20   # % players with Overall Score ≥ 4.25
    + positional_diversity * 0.10   # normalised Shannon entropy
    + team_diversity       * 0.10
    + depth_score          * 0.10
```
