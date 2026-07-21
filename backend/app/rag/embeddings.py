"""Lexical search (TF-IDF / BM25) implementation built from scratch.

Satisfies strict scratch mode requirements — no pretrained weights or external
embeddings libraries required.
"""
from __future__ import annotations

import math
import re
from collections import Counter


def tokenize(text: str) -> list[str]:
    """Lowercase text and split into words."""
    return re.findall(r"\w+", text.lower())


class LexicalIndex:
    """TF-IDF based search engine for ranking text chunks."""

    def __init__(self, chunks: list[str]):
        self.chunks = chunks
        self.doc_count = len(chunks)
        self.doc_tokens = [tokenize(c) for c in chunks]
        
        # Calculate term frequencies (TF) for each document
        self.tfs = [Counter(tokens) for tokens in self.doc_tokens]
        
        # Calculate document frequencies (DF) for each term
        self.dfs = Counter()
        for tokens in self.doc_tokens:
            unique_terms = set(tokens)
            for term in unique_terms:
                self.dfs[term] += 1
                
        # Calculate inverse document frequencies (IDF)
        self.idfs = {}
        for term, df in self.dfs.items():
            # Standard smoothed IDF formula
            self.idfs[term] = math.log((self.doc_count + 1) / (df + 0.5)) + 1

    def search(self, query: str, top_k: int = 5) -> list[tuple[int, float]]:
        """Return the indices of the top ranked chunks with their score."""
        query_tokens = tokenize(query)
        if not query_tokens or self.doc_count == 0:
            return []
            
        scores = []
        for i in range(self.doc_count):
            doc_tf = self.tfs[i]
            doc_len = len(self.doc_tokens[i])
            if doc_len == 0:
                continue
                
            score = 0.0
            for term in query_tokens:
                if term in doc_tf:
                    # Simple TF-IDF score
                    tf = doc_tf[term] / doc_len
                    idf = self.idfs.get(term, 0.0)
                    score += tf * idf
            if score > 0:
                scores.append((i, score))
                
        # Sort descending by score
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]
