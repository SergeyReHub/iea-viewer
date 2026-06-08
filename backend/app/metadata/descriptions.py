from pathlib import Path

DOCS_ROOT = Path(__file__).parent / "descriptions"


def load_table_markdown(doc_file: str) -> str:
    full_path = DOCS_ROOT / doc_file
    if not full_path.exists():
        return "Описание для таблицы пока не найдено."
    return full_path.read_text(encoding="utf-8")
