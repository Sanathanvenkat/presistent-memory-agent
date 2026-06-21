# Persistent Memory Customer Agent

> Stateless agents are toys. Here's what a real memory architecture looks like.

Customer support agent that remembers every customer across sessions using a 3-layer memory architecture.

## Memory Architecture

```
User Message
     │
     ▼
┌─────────────────────────────────────────────────┐
│  Layer 1: Short-term memory                     │
│  Current conversation context in LangGraph state│
└─────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────┐
│  Layer 2: Session memory (Mem0)                 │
│  Extracts facts after each turn:                │
│  name, plan, issues, preferences, sentiment     │
└─────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────┐
│  Layer 3: Long-term memory (Redis / fakeredis)  │
│  Persists facts across sessions permanently     │
│  Key: customer_memory:{customer_id}             │
└─────────────────────────────────────────────────┘
     │
     ▼
Next session: agent loads all 3 layers before responding
```

## LangGraph Flow

```
memory_load → agent_node → memory_update → END
```

- `memory_load` — fetches Redis facts + Mem0 semantic search before LLM call
- `agent_node` — responds with full customer context in system prompt
- `memory_update` — extracts new facts and persists to Redis after response

## What the agent remembers

| Fact type | Example |
|---|---|
| Name | "Customer's name is Priya" |
| Plan | "Customer is on the Pro plan" |
| Past issues | "Customer had a billing issue in previous session" |
| Preferences | "Customer prefers email communication" |
| Sentiment | "Customer expressed frustration with refund process" |

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # add GROQ_API_KEY
```

**Production Redis swap** — in `memory/store.py`, replace:
```python
# Dev
_redis = fakeredis.FakeRedis(decode_responses=True)

# Production
import redis
_redis = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)
```

## Run

```bash
uvicorn api:app --reload
```

Swagger UI: http://localhost:8000/docs

## Demo flow

```bash
# Step 1 — first contact, no memory
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust_001", "message": "Hi, my name is Priya and I have a billing issue on my Pro plan"}'

# Step 2 — follow-up, agent remembers name + issue
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust_001", "message": "Is my refund being processed?"}'

# Step 3 — new session, agent still remembers everything
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"customer_id": "cust_001", "message": "Hey, I am back. Any updates?"}'

# View all memories
curl http://localhost:8000/memory/cust_001

# GDPR erase
curl -X DELETE http://localhost:8000/memory/cust_001
```

## Key concepts demonstrated

- **3-layer memory** — short-term, session, long-term working together
- **Mem0** — purpose-built memory extraction (deduplication, merging)
- **Redis** (fakeredis in dev) — persistent key-value store per customer
- **LangGraph** — memory load/update as explicit graph nodes
- **GDPR compliance** — DELETE endpoint erases all customer data
- **Production-ready swap** — one line to go from fakeredis to Redis