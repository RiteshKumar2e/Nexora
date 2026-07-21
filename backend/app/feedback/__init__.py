"""User-feedback capture + RLHF data collection.

Every rated turn (from any backend — native nano-llm or Groq) is appended to a
single JSON-Lines file, which the native model can then be fine-tuned on. Groq's
hosted weights can't be retrained, so its interactions feed the SAME native-model
training set (and a preference dataset), never a Groq fine-tune.
"""
