import os
import sys

# we ensure src is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.models.config import AnalysisConfig
from src.services.pipeline_service import process_log_file as run_pipeline_file


def process_log_file(filepath: str, db_path: str = "safenet.db", config: AnalysisConfig | None = None):
    """
    Orchestrates the entire SafeNet pipeline:
    1. loads data
    2. parses into Messages
    3. runs through Risk Engine
    4. saves results to SQLite
    """
    config = config or AnalysisConfig()

    print(f"> Starting SafeNet Processing Pipeline")
    print(f"Loading file: {filepath}")
    print(f"Config: threshold={config.toxicity_threshold}, window={config.escalation_window_size}")

    print("Analyzing messages through Risk Engine (Batch Mode)...")
    msg_count, alert_count = run_pipeline_file(
        filepath=filepath,
        db_path=db_path,
        config=config,
        generate_reports=True,
    )
    print(f"Data successfully saved to {db_path}.")

    print("> Pipeline Execution Finished")
    return msg_count, alert_count


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_chat_log>")
        sys.exit(1)

    log_file = sys.argv[1]
    process_log_file(log_file)
