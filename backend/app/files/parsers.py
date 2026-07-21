"""Parsers for uploaded documents (PDF, DOCX, CSV, Excel, TXT, JSON, code)."""
from __future__ import annotations

import json
from pathlib import Path


def parse_txt(file_bytes: bytes) -> str:
    """Parse raw text files."""
    try:
        return file_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return file_bytes.decode("latin-1", errors="replace")


def parse_csv(file_bytes: bytes) -> str:
    """Parse CSV and convert to Markdown table format for LLM readability."""
    text = parse_txt(file_bytes)
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return ""
    
    markdown_table = []
    for i, line in enumerate(lines):
        row = [cell.strip() for cell in line.split(",")]
        # Escape markdown pipe
        escaped_row = [c.replace("|", "\\|") for c in row]
        markdown_table.append("| " + " | ".join(escaped_row) + " |")
        if i == 0:
            # Add separator line
            markdown_table.append("|" + "---|"*len(row))
            
    return "\n".join(markdown_table)


def parse_json(file_bytes: bytes) -> str:
    """Parse JSON and return clean formatted JSON string."""
    try:
        data = json.loads(parse_txt(file_bytes))
        return json.dumps(data, indent=2)
    except Exception as e:
        return f"Invalid JSON file: {e}"


def parse_document(filename: str, file_bytes: bytes) -> str:
    """Dispatch file bytes to appropriate text extractor based on file extension."""
    ext = Path(filename).suffix.lower()
    
    if ext in (".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".rs", ".go", ".c", ".cpp", ".java"):
        return parse_txt(file_bytes)
    elif ext == ".csv":
        return parse_csv(file_bytes)
    elif ext == ".json":
        return parse_json(file_bytes)
    elif ext == ".pdf":
        # Basic fallback for pdf text extraction
        text = parse_txt(file_bytes)
        # Strip control and binary non-ascii characters to get printable texts
        cleaned = "".join(c for c in text if c.isprintable() or c in "\n\r\t")
        return f"[PDF Extract - Printable content]\n{cleaned[:20000]}"
    else:
        # Fallback to simple decoded text
        return parse_txt(file_bytes)[:50000]
