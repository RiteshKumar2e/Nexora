"""Nexora's from-scratch language model package.

This package contains:
- BPE tokenizer (trained from scratch)
- Transformer decoder (causal, with RoPE + SwiGLU + RMSNorm)
- Inference engine (temperature, top-k, top-p, repetition penalty)
- Training loops (pretraining + instruction tuning)
- Dataset utilities

No pretrained weights, no Hugging Face models, no external LLM dependencies.
Everything is built from random initialization.
"""
