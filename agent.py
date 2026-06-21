"""
agent.py
────────
LangGraph customer support agent with 3-layer persistent memory.

Graph:
  memory_load → agent_node → memory_update → END

memory_load  — builds context from Redis + Mem0 before the LLM sees the query
agent_node   — calls Groq with memory-enriched system prompt
memory_update — extracts new facts and persists them after the response
"""

import os
from typing import TypedDict
from openai import OpenAI
from langgraph.graph import StateGraph, END
from dotenv import load_dotenv
from memory.manager import memory_manager

load_dotenv()

_client = OpenAI(
    api_key=os.environ["GROQ_API_KEY"],
    base_url="https://api.groq.com/openai/v1",
)

MODEL = "llama-3.3-70b-versatile"

BASE_SYSTEM = """You are a knowledgeable customer support agent.

You have access to the customer's history from previous sessions.
Use this context naturally — greet returning customers by name if you know it,
reference their past issues, remember their preferences.

Never ask for information you already have in the customer context.
Be concise, warm, and helpful.
"""


# ── State ─────────────────────────────────────────────────────────────────────

class AgentState(TypedDict):
    customer_id:      str
    user_message:     str
    memory_context:   str
    agent_response:   str
    new_memories:     list[dict]
    is_returning:     bool


# ── Nodes ─────────────────────────────────────────────────────────────────────

def memory_load(state: AgentState) -> AgentState:
    """Layer 1+2+3 — build memory context before agent responds."""
    customer_id = state["customer_id"]
    state["is_returning"] = memory_manager.has_history(customer_id)
    state["memory_context"] = memory_manager.build_context(
        customer_id, state["user_message"]
    )
    return state


def agent_node(state: AgentState) -> AgentState:
    """Calls LLM with memory-enriched system prompt."""
    system = f"""{BASE_SYSTEM}

--- Customer Memory Context ---
{state["memory_context"]}
--- End Context ---

Customer ID: {state["customer_id"]}
{"(Returning customer)" if state["is_returning"] else "(New customer — no prior history)"}
"""
    response = _client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user",   "content": state["user_message"]},
        ],
        max_tokens=512,
        temperature=0.4,
    )
    state["agent_response"] = response.choices[0].message.content.strip()
    return state


def memory_update(state: AgentState) -> AgentState:
    """Extracts new facts from this turn and persists them."""
    messages = [
        {"role": "user",      "content": state["user_message"]},
        {"role": "assistant", "content": state["agent_response"]},
    ]
    try:
        new = memory_manager.update_memory(state["customer_id"], messages)
        state["new_memories"] = new
    except Exception:
        state["new_memories"] = []
    return state


# ── Graph ─────────────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("memory_load",   memory_load)
    graph.add_node("agent_node",    agent_node)
    graph.add_node("memory_update", memory_update)

    graph.set_entry_point("memory_load")
    graph.add_edge("memory_load",   "agent_node")
    graph.add_edge("agent_node",    "memory_update")
    graph.add_edge("memory_update", END)

    return graph.compile()


_graph = build_graph()


def chat(customer_id: str, message: str) -> dict:
    """Entry point — sends a message and returns response + memory state."""
    result = _graph.invoke(AgentState(
        customer_id    = customer_id,
        user_message   = message,
        memory_context = "",
        agent_response = "",
        new_memories   = [],
        is_returning   = False,
    ))
    return result