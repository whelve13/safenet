# SafeNet

A Python-based tool for detecting and reporting online harassment and toxic behavior in chat logs. SafeNet processes conversation data through a multi-stage analysis pipeline, flags risky messages, profiles repeat offenders, and generates actionable moderation reports.

> Built as a university project exploring digital tools for preventing online harassment and cyberbullying.

---

## Features

- **Toxicity Detection** — Scores messages against a configurable risk threshold
- **Risk Engine** — Tracks escalation patterns across a sliding message window
- **User Profiling** — Maintains per-user offense history using a custom HashMap structure
- **Automated Alerting** — Generates alerts for flagged messages and escalation events
- **Report Generation** — Exports a CSV of all alerts and a ranked top-offenders summary
- **SQLite Persistence** — Stores all messages, users, and alerts in a local database
- **Multi-format Input** — Accepts both `.json` and `.txt` chat log files

---
## Project Structure

```
safenet/
├── main.py                  # Entry point — orchestrates the full pipeline
├── requirements.txt
└── src/
    ├── parser/
    │   ├── file_loader.py   # Loads .json and .txt chat files
    │   └── chat_parser.py   # Parses raw data into Message objects
    ├── models/
    │   └── config.py        # AnalysisConfig (threshold, window size, etc.)
    ├── algorithms/
    │   └── risk_engine.py   # Core toxicity scoring and escalation logic
    ├── database/
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
```

### Usage

Run the pipeline on a chat log file:

```bash
python main.py <path_to_chat_log>
```

**Example:**
```bash
python main.py data/sample_chat.json
```

SafeNet accepts both `.json` and `.txt` chat log formats. After processing, results are saved to `safenet.db` and two report files are generated automatically.

---

## Output

| File                |  Description                                         |
|---------------------|------------------------------------------------------|
| `safenet.db`        | SQLite database with all messages, users, and alerts |
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

---

## Motivation

Online harassment and cyberbullying cause serious psychological harm, yet most platforms lack proactive moderation tools. SafeNet was developed as an academic exploration of how automated text analysis and behavioral pattern detection can assist human moderators in identifying and responding to harmful content faster.
