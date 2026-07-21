"""Orchestrator for lexical RAG retrieval and query building."""
from __future__ import annotations

import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.file import UploadedFile
from app.rag.chunker import split_text
from app.rag.embeddings import LexicalIndex


async def retrieve_rag_context(
    db: AsyncSession,
    query: str,
    project_id: Optional[uuid.UUID] = None,
    user_id: Optional[uuid.UUID] = None,
    top_k: int = 4
) -> tuple[str, list[dict]]:
    """Query all project files, rank matching chunks, and format context blocks."""
    # 1. Fetch files in project context
    stmt = select(UploadedFile)
    if user_id:
        stmt = stmt.where(UploadedFile.user_id == user_id)
    else:
        stmt = stmt.where(UploadedFile.user_id.is_(None))
        
    if project_id:
        stmt = stmt.where(UploadedFile.project_id == project_id)
        
    res = await db.execute(stmt)
    files = res.scalars().all()
    
    if not files:
        return "", []

    # 2. Build flat list of chunks mapping back to parent file
    all_chunks = []
    chunk_metadata = []
    
    for f in files:
        if not f.parsed_text:
            continue
        chunks = split_text(f.parsed_text)
        for chunk in chunks:
            all_chunks.append(chunk)
            chunk_metadata.append({
                "file_id": f.id,
                "filename": f.filename,
                "chunk": chunk
            })
            
    if not all_chunks:
        return "", []

    # 3. Score chunks using LexicalIndex BPE matching
    indexer = LexicalIndex(all_chunks)
    matches = indexer.search(query, top_k=top_k)
    
    if not matches:
        return "", []

    # 4. Generate clean prompt reference block
    context_blocks = []
    citations = []
    
    for idx, score in matches:
        meta = chunk_metadata[idx]
        citation_num = len(citations) + 1
        
        context_blocks.append(
            f"Source Document Reference [{citation_num}]: {meta['filename']}\n"
            f"Content:\n{meta['chunk']}\n"
        )
        
        citations.append({
            "citation_index": citation_num,
            "filename": meta["filename"],
            "file_id": str(meta["file_id"]),
            "snippet": meta["chunk"][:120] + "..."
        })
        
    context_str = (
        "Here are reference documents and snippets that you should use to base your answer on. "
        "Maintain citations (e.g. Reference [1]) whenever citing their details:\n\n" +
        "\n---\n".join(context_blocks)
    )
    
    return context_str, citations
