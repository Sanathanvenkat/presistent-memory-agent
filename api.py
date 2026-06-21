"""
api.py
──────
FastAPI app for the persistent memory customer agent.

Endpoints:
  POST /chat                        — send a message as a customer
  GET  /memory/{customer_id}        — view all memories for a customer
  DELETE /memory/{customer_id}      — erase all memories (GDPR)
  GET  /health                      — health check
  GET  /examples                    — demo flow to test with

Run:
  uvicorn api:app --reload
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from agent import chat
from memory.manager import memory_manager

app = FastAPI(
    title="Persistent Memory Customer Agent",
    description=(
        "Customer support agent with 3-layer memory architecture:\n"
        "- Layer 1: Short-term (conversation context in state)\n"
        "- Layer 2: Session (Mem0 extracts facts after each turn)\n"
        "- Layer 3: Long-term (fakeredis persists across sessions)\n\n"
        "Swap fakeredis → redis.Redis() for production."
    ),
    version="1.0.0",
)


class ChatRequest(BaseModel):
    customer_id: str = Field(..., description="Unique customer identifier")
    message:     str = Field(..., description="Customer's message")


class ChatResponse(BaseModel):
    customer_id:   str
    response:      str
    is_returning:  bool
    new_memories:  list[dict]
    memory_context: str


@app.get("/health")
async def health():
    return {"status": "ok", "memory_layers": 3, "storage": "fakeredis (swap → Redis for prod)"}


@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Send a message as a customer.

    The agent automatically:
    1. Loads memory context from Redis + Mem0
    2. Responds with awareness of past interactions
    3. Extracts and stores new facts from this conversation

    Try the same customer_id across multiple requests to see memory in action.
    """
    if not request.message.strip():
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    try:
        result = chat(request.customer_id, request.message)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Agent error: {e}")

    return ChatResponse(
        customer_id    = request.customer_id,
        response       = result["agent_response"],
        is_returning   = result["is_returning"],
        new_memories   = result["new_memories"],
        memory_context = result["memory_context"],
    )


@app.get("/memory/{customer_id}")
async def get_memory(customer_id: str):
    """View all stored memories for a customer."""
    memories = memory_manager.get_all(customer_id)
    return {
        "customer_id": customer_id,
        "has_history": memory_manager.has_history(customer_id),
        **memories
    }


@app.delete("/memory/{customer_id}")
async def delete_memory(customer_id: str):
    """
    Erase all memories for a customer.
    GDPR right to erasure — permanently deletes from Redis and Mem0.
    """
    memory_manager.clear(customer_id)
    return {"customer_id": customer_id, "status": "all memories erased"}


@app.get("/examples")
async def examples():
    return {
        "demo_flow": {
            "step_1": {
                "description": "First contact — agent has no memory",
                "request": {"customer_id": "cust_001", "message": "Hi, my name is Priya and I'm having trouble with my billing on the Pro plan"}
            },
            "step_2": {
                "description": "Follow-up — agent remembers name and issue",
                "request": {"customer_id": "cust_001", "message": "Is my refund request being processed?"}
            },
            "step_3": {
                "description": "New session — agent still remembers everything",
                "request": {"customer_id": "cust_001", "message": "Hey, I'm back. Did anything change with my account?"}
            },
        },
        "memory_check": "GET /memory/cust_001 — see all extracted facts",
        "gdpr_erase":   "DELETE /memory/cust_001 — wipe all customer data",
    }