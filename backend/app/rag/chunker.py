"""Document text chunker for the RAG pipeline."""
from __future__ import annotations


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks of a given character size."""
    if not text:
        return []
        
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = min(start + chunk_size, text_len)
        
        # If we are not at the end of the text, try to split at a word boundary
        if end < text_len:
            # Look backward for whitespace or punctuation to avoid cutting words
            last_space = text.rfind(" ", start, end)
            if last_space != -1 and last_space > start:
                end = last_space
                
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
            
        start = end - chunk_overlap
        if start >= text_len or end == text_len:
            break
            
        # Ensure we always make progress
        if start < 0:
            start = 0
            
    return chunks
