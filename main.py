import os
import sys

# we ensure src is in the path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

from src.parser.file_loader import FileLoader
from src.parser.chat_parser import ChatParser
from src.models.config import AnalysisConfig
from src.algorithms.risk_engine import RiskEngine
from src.database.repository import DatabaseRepository
from src.reports.report_generator import ReportGenerator


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

    loader = FileLoader()
    parser = ChatParser()

    if filepath.endswith('.json'):
        raw_data = loader.load_json(filepath)
        messages = parser.parse_json_records(raw_data)
    else:
        raw_data = loader.load_txt(filepath)
        messages = parser.parse_txt_lines(raw_data)

    print(f"Parsed {len(messages)} messages successfully.")

    engine = RiskEngine(config)
    print("Analyzing messages through Risk Engine...")
    for msg in messages:
        engine.process_message(msg)

    print("Analysis complete. Persisting data to SQLite...")
    repo = DatabaseRepository(db_path)
    repo.clear_all_data()

    # save all analyzed messages
    for msg in messages:
        repo.save_message(msg)

    # save all updated users (from our Custom HashMap)
    for user in engine.users.values():
        repo.save_user(user)

    # save all generated alerts
    for alert in engine.alerts:
        repo.save_alert(alert)

    print(f"Data successfully saved to {db_path}.")

    # generate automatic reports
    report_gen = ReportGenerator(repo)
    report_gen.generate_alerts_csv()
    report_gen.generate_top_offenders_txt()

    print("> Pipeline Execution Finished")
    return len(messages), len(engine.alerts)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python main.py <path_to_chat_log>")
        sys.exit(1)

    log_file = sys.argv[1]
    process_log_file(log_file)
