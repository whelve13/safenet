import os
import tempfile
from typing import Tuple

from src.algorithms.risk_engine import RiskEngine
from src.database.repository import DatabaseRepository
from src.models.config import AnalysisConfig
from src.models.message import Message
from src.parser.chat_parser import ChatParser
from src.parser.file_loader import FileLoader
from src.reports.report_generator import ReportGenerator


def _load_messages(filepath: str) -> list[Message]:
    loader = FileLoader()
    parser = ChatParser()

    if filepath.endswith(".json"):
        raw_data = loader.load_json(filepath)
        return parser.parse_json_records(raw_data)

    raw_data = loader.load_txt(filepath)
    return parser.parse_txt_lines(raw_data)


def _process_messages(
    messages: list[Message],
    repo: DatabaseRepository,
    config: AnalysisConfig,
    clear_existing_data: bool = True,
) -> Tuple[int, int]:
    engine = RiskEngine(config)
    engine.process_messages_batch(messages)

    if clear_existing_data:
        repo.clear_all_data()

    for msg in messages:
        repo.save_message(msg)
    for user in engine.users.values():
        repo.save_user(user)
    for alert in engine.alerts:
        repo.save_alert(alert)

    return len(messages), len(engine.alerts)


def process_log_file(
    filepath: str,
    db_path: str = "safenet.db",
    config: AnalysisConfig | None = None,
    generate_reports: bool = True,
) -> Tuple[int, int]:
    cfg = config or AnalysisConfig()
    messages = _load_messages(filepath)
    repo = DatabaseRepository(db_path)
    msg_count, alert_count = _process_messages(messages, repo, cfg)

    if generate_reports:
        report_gen = ReportGenerator(repo)
        report_gen.generate_alerts_csv()
        report_gen.generate_top_offenders_txt()

    return msg_count, alert_count


def process_uploaded_file_bytes(
    file_bytes: bytes,
    filename: str,
    repo: DatabaseRepository,
    config: AnalysisConfig,
) -> Tuple[int, int]:
    suffix = os.path.splitext(filename)[1] or ".txt"
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix, mode="wb")
    tmp.write(file_bytes)
    tmp.close()

    try:
        messages = _load_messages(tmp.name)
        return _process_messages(messages, repo, config)
    finally:
        os.unlink(tmp.name)

