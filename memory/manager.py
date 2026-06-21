"""
memory/manager.py
──────────────────
Unified memory interface combining all 3 layers.

Layer 1 — Short-term  : conversation history (in LangGraph state)
Layer 2 — Session     : Mem0 extracts facts after each turn
Layer 3 — Long-term   : Redis persists facts across sessions

The agent calls this manager — it never talks to Mem0 or Redis directly.
Clean separation: agent logic vs memory logic.
"""

from memory.extractor import extract_memories, search_memories, get_all_memories
from memory.store import save_memories, load_memories, delete_memories, memory_exists


class MemoryManager:

    def build_context(self, customer_id: str, current_query: str) -> str:
        """
        Builds a memory context string to inject into the agent's system prompt.
        Combines Redis long-term facts + Mem0 semantic search results.
        """
        context_parts = []

        # Layer 3 — Redis: load persisted facts from previous sessions
        redis_memories = load_memories(customer_id)
        if redis_memories:
            facts = "\n".join(f"  - {m.get('memory', m)}" for m in redis_memories[:8])
            context_parts.append(f"Known facts about this customer (from past sessions):\n{facts}")

        # Layer 2 — Mem0: semantic search for relevant memories
        mem0_results = search_memories(customer_id, current_query, limit=3)
        if mem0_results:
            relevant = "\n".join(f"  - {m.get('memory', '')}" for m in mem0_results if m.get('memory'))
            if relevant.strip():
                context_parts.append(f"Relevant context for this query:\n{relevant}")

        if not context_parts:
            return "No prior history for this customer."

        return "\n\n".join(context_parts)

    def update_memory(self, customer_id: str, messages: list[dict]) -> list[dict]:
        """
        Called after each conversation turn.
        Extracts new facts via Mem0 and persists to Redis.
        """
        # Extract new facts from conversation
        new_memories = extract_memories(customer_id, messages)

        # Merge with existing Redis memories (deduplicate by memory text)
        existing = load_memories(customer_id)
        existing_texts = {m.get("memory", "") for m in existing}

        merged = list(existing)
        for mem in new_memories:
            text = mem.get("memory", "")
            if text and text not in existing_texts:
                merged.append({"memory": text})
                existing_texts.add(text)

        # Persist back to Redis
        save_memories(customer_id, merged)
        return new_memories

    def get_all(self, customer_id: str) -> dict:
        """Returns full memory state for a customer."""
        return {
            "redis_memories": load_memories(customer_id),
            "mem0_memories":  get_all_memories(customer_id),
        }

    def clear(self, customer_id: str) -> None:
        """Deletes all memories for a customer (GDPR right to erasure)."""
        delete_memories(customer_id)

    def has_history(self, customer_id: str) -> bool:
        return memory_exists(customer_id)


# Singleton
memory_manager = MemoryManager()