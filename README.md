# SafeNet

A Python-based tool for detecting and reporting online harassment and toxic behavior in chat logs and live browser content. SafeNet now supports:
- manual chat-log analysis (CLI + Streamlit dashboard)
- live API-powered moderation for a Chromium extension
- persisted moderation audit events in SQLite

> Built as a university project exploring digital tools for preventing online harassment and cyberbullying.

---

## Features

- **Toxicity Detection** — Scores messages against a configurable risk threshold
- **Hybrid Scoring Path** — Dictionary probing first, then `unitary/toxic-bert` fallback when dictionary confidence is below 0.8
- **Risk Engine** — Tracks escalation patterns across a sliding message window
- **User Profiling** — Maintains per-user offense history using a custom HashMap structure
- **Automated Alerting** — Generates alerts for flagged messages and escalation events
- **Report Generation** — Exports a CSV of all alerts and a ranked top-offenders summary
- **FastAPI Backend** — Exposes `/health`, `/model-info`, `/v1/analyze/text`, `/v1/analyze/batch`
- **Extension Audit Log** — Persists real moderation events (`blur` / `block`) in `moderation_events`
- **SQLite Persistence** — Stores messages, users, alerts, and extension/API moderation events
- **Multi-format Input** — Accepts both `.json` and `.txt` chat log files

---
## Project Structure

```
safenet/
├── main.py                  # Entry point — orchestrates the full pipeline
├── requirements.txt
├── extension/               # Chromium MV3 extension
└── src/
    ├── api/
    │   ├── app.py           # FastAPI app and endpoints
    │   └── schemas.py       # Request/response contracts
    ├── services/
    │   ├── pipeline_service.py    # Shared file-analysis orchestration
    │   └── moderation_service.py  # Shared live moderation scoring + mapping
    ├── parser/
    │   ├── file_loader.py   # Loads .json and .txt chat files
    │   └── chat_parser.py   # Parses raw data into Message objects
    ├── models/
    │   └── config.py        # AnalysisConfig (threshold, window size, etc.)
    ├── algorithms/
    │   └── risk_engine.py   # Core toxicity scoring and escalation logic
    ├── database/
    │   ├── schema.py        # SQLite tables (including moderation_events)
    │   └── repository.py    # SQLite read/write via DatabaseRepository
    └── reports/
        └── report_generator.py  # Generates CSV and TXT reports
```

---

## Getting Started

### Prerequisites

- Python 3.10+

### Installation

```bash
git clone https://github.com/whelve13/safenet.git
cd safenet
pip install -r requirements.txt
pip install -r requirements-ml.txt
```

### Usage

### 1) Manual file analysis (CLI)

Run the pipeline on a chat log file:

```bash
python main.py <path_to_chat_log>
```

**Example:**
```bash
python main.py data/sample_chat.json
```

SafeNet accepts both `.json` and `.txt` chat log formats. After processing, results are saved to `safenet.db` and two report files are generated automatically.

### 2) Streamlit dashboard (two modes)

```bash
streamlit run src/dashboard/app.py
```

Dashboard now includes:
- **Manual File Analysis** — existing upload + scan workflow
- **Extension Audit** — reads real events stored by API/extension detections

### 3) FastAPI backend

```bash
uvicorn src.api.app:app --host 127.0.0.1 --port 8000 --reload
```

Available endpoints:
- `GET /health`
- `GET /model-info`
- `POST /v1/analyze/text`
- `POST /v1/analyze/batch`

Useful checks:
- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

### 4) Chromium extension (MV3)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `extension/` folder
5. Keep API running (`uvicorn ...`)
6. Open the extension popup and set:
   - API URL: `http://127.0.0.1:8000`
   - scanning: enabled
   - severity threshold: `medium` (or preferred level)
7. Click **Check API** in popup, then test on a page with user-entered or visible text

### 5) Quick test flow (API + extension + audit)

1. Start API (`uvicorn ...`) in terminal A.
2. Load extension and enable scanning in browser.
3. Visit any page and try text like `you are an idiot` or `go die`.
4. Confirm blur/tooltip behavior in browser.
5. Start dashboard in terminal B:
   ```bash
   streamlit run src/dashboard/app.py
   ```
6. Open **Extension Audit** tab to view recorded moderation events.

---

## Output

| File                |  Description                                         |
|---------------------|------------------------------------------------------|
| `safenet.db`        | SQLite database with messages, users, alerts, and moderation_events |
| `alerts_report.csv` | All flagged messages with timestamps and scores      |
| `top_offenders.txt` | Ranked list of users by offense severity             |

---

## Configuration

You can customize analysis behavior by passing an `AnalysisConfig` object when calling `process_log_file()` programmatically:

```python
from src.models.config import AnalysisConfig
from main import process_log_file

config = AnalysisConfig(toxicity_threshold=0.7, escalation_window_size=10)
process_log_file("data/chat.json", config=config)
```

---

## Dependencies

| Package      |  Purpose                                 |
|--------------|------------------------------------------|
| `streamlit`  | Visual dashboard / moderation UI         |
| `pandas`     | Data manipulation and report export      |
| `matplotlib` | Visualizations and charts                |
| `networkx`   | Interaction graph modeling between users |
| `fpdf2`      | PDF report generation                    |
| `fastapi`    | API service for live moderation          |
| `uvicorn`    | ASGI server for FastAPI                  |

---

## Motivation

Online harassment and cyberbullying cause serious psychological harm, yet most platforms lack proactive moderation tools. SafeNet was developed as an academic exploration of how automated text analysis and behavioral pattern detection can assist human moderators in identifying and responding to harmful content faster.
