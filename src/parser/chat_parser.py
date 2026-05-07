import re
import sys
import os
from datetime import datetime

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.models.message import Message

class ChatParser:
    # parses raw chat logs into structured Message objects
    def __init__(self):
        # sample format - [2023-10-27 14:30:00] UserA -> UserB: You are stupid!
        # or broadcast - [2023-10-27 14:31:00] UserA: Hello everyone
        self.txt_pattern = re.compile(
            r'\[(.*?)\]\s+([\w\s]+?)(?:\s*->\s*([\w\s]+?))?:\s*(.*)'
        )

    def parse_txt_lines(self, lines: list[str]) -> list[Message]:
        messages = []
        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue
                
            match = self.txt_pattern.match(line)
            if match:
                time_str, sender, receiver, content = match.groups()
                try:
                    timestamp = datetime.strptime(time_str, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    timestamp = datetime.now() # fallback if parsing fails
                    
                message = Message(
                    id=f"MSG-TXT-{i}",
                    timestamp=timestamp,
                    sender_id=sender.strip(),
                    receiver_id=receiver.strip() if receiver else None,
                    content=content.strip()
                )
                messages.append(message)
        return messages

    def parse_json_records(self, records: list[dict]) -> list[Message]:
        messages = []
        for i, record in enumerate(records):
            # Expecting schema: {"time": "...", 
            #                    "sender": "...",
            #                    "target": "...",
            #                    "message": "..."}
            try:
                timestamp = datetime.fromisoformat(record.get("time", 
                                                   datetime.now().isoformat()))
            except ValueError:
                timestamp = datetime.now()

            sender = record.get("sender")
            if not sender or not record.get("msg"):
                continue

            msg = Message(
                id=f"MSG-JSON-{i}",
                timestamp=timestamp,
                sender_id=sender,
                receiver_id=record.get("target"),
                content=record.get("msg", "")
            )
            messages.append(msg)
        return messages
