"""
memory/extractor.py
────────────────────
Layer 2 — Memory extraction using Mem0.
Updated to use new Mem0 API (filters instead of user_id in search).
"""

import os
from mem0 import Memory
from dotenv import load_dotenv

load_dotenv()

MEM0_CONFIG = {
    "llm": {
        "provider": "groq",
        "config": {
            "model":   "llama-3.3-70b-versatile",
            "api_key": os.environ.get("GROQ_API_KEY", ""),
        }
    },
    "embedder": {
        "provider": "huggingface",
        "config": {
            "model": "multi-qa-MiniLM-L6-cos-v1"
        }
    },
    "vector_store": {
        "provider": "qdrant",
        "config": {
            "collection_name":      "customer_memories",
            "embedding_model_dims": 384,
            "on_disk":              False,
        }
    }
}

_mem0 = None

def get_mem0() -> Memory:
    global _mem0
    if _mem0 is None:
        _mem0 = Memory.from_config(MEM0_CONFIG)
    return _mem0


def extract_memories(customer_id: str, messages: list[dict]) -> list[dict]:
    mem    = get_mem0()
    result = mem.add(messages, user_id=customer_id)
    return result.get("results", []) if isinstance(result, dict) else []


def search_memories(customer_id: str, query: str, limit: int = 5) -> list[dict]:
    mem = get_mem0()
    try:
        # New Mem0 API — use filters instead of user_id
        results = mem.search(
            query,
            filters={"user_id": customer_id},
            limit=limit
        )
    except TypeError:
        # Fallback for older Mem0 versions
        results = mem.search(query, user_id=customer_id, limit=limit)
    return results.get("results", []) if isinstance(results, dict) else []


def get_all_memories(customer_id: str) -> list[dict]:
    mem     = get_mem0()
    results = mem.get_all(user_id=customer_id)
    return results.get("results", []) if isinstance(results, dict) else []