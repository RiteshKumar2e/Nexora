"""Unit tests for the Nexora Native Model and RAG pipeline."""
import os
import sys
import unittest

# Ensure project root is in PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import torch
import tempfile

from nexora_model.config import NexoraModelConfig
from nexora_model.tokenizer import NexoraTokenizer
from nexora_model.transformer import NexoraTransformer
from nexora_model.inference import NexoraGenerator
from app.rag.chunker import split_text
from app.rag.embeddings import LexicalIndex


class TestTokenizer(unittest.TestCase):
    def setUp(self):
        # Train a small BPE tokenizer on simple samples
        self.texts = [
            "hello world",
            "hello machine learning",
            "python is great",
            "the internet is a global network"
        ]
        self.tokenizer = NexoraTokenizer.train(self.texts, vocab_size=100)

    def test_encode_decode(self):
        text = "hello python is learning"
        ids = self.tokenizer.encode(text)
        decoded = self.tokenizer.decode(ids, skip_special=True)
        self.assertIn("hello", decoded)
        self.assertIn("python", decoded)

    def test_special_tokens(self):
        text = "<|system|>You are Nexora<|user|>Hello"
        ids = self.tokenizer.encode(text)
        self.assertIn(4, ids)  # <|system|> token ID
        self.assertIn(5, ids)  # <|user|> token ID


class TestTransformer(unittest.TestCase):
    def setUp(self):
        self.config = NexoraModelConfig(
            vocab_size=100,
            d_model=64,
            n_layers=2,
            n_heads=2,
            max_seq_len=32
        )
        self.model = NexoraTransformer(self.config)

    def test_forward_pass(self):
        # Batch size 2, Sequence length 8
        input_ids = torch.randint(0, 100, (2, 8))
        res = self.model(input_ids)
        self.assertEqual(res["logits"].shape, (2, 8, 100))

    def test_forward_pass_with_loss(self):
        input_ids = torch.randint(0, 100, (2, 8))
        labels = torch.randint(0, 100, (2, 8))
        res = self.model(input_ids, labels=labels)
        self.assertIn("loss", res)
        self.assertTrue(res["loss"].item() > 0)


class TestRAGPipeline(unittest.TestCase):
    def test_chunker(self):
        text = "This is a very long sentence that we want to split into smaller segments for context processing."
        chunks = split_text(text, chunk_size=30, chunk_overlap=10)
        self.assertTrue(len(chunks) > 1)
        for chunk in chunks:
            self.assertTrue(len(chunk) <= 30)

    def test_lexical_search(self):
        chunks = [
            "Python is a popular programming language.",
            "Photosynthesis converts light energy to chemical glucose.",
            "The internet relies on global routers and standard TCP/IP."
        ]
        indexer = LexicalIndex(chunks)
        matches = indexer.search("photosynthesis", top_k=1)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0], 1)  # Index of the photosynthesis chunk


if __name__ == "__main__":
    unittest.main()
