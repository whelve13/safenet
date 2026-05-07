import os
import json

class FileLoader:
    """
    Utility class for loading raw data from various file formats.
    """
    @staticmethod
    def load_txt(filepath: str) -> list[str]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.readlines()

    @staticmethod
    def load_json(filepath: str) -> list[dict]:
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        with open(filepath, 'r', encoding='utf-8') as file:
            return json.load(file)
