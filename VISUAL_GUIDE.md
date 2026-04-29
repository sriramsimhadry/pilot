# Aeroo Incomplete Input Handling - Visual Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (UI)                            │
│  Shows questions → User types response → Sends clarification    │
└──────────────────────────┬──────────────────────────────────────┘
                           │
                 WebSocket & HTTP API
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   FastAPI Backend (main.py)                     │
│                                                                  │
│  POST /api/workflow/start                                       │
│  POST /api/workflow/{id}/clarify                                │
│  GET  /api/workflow/{id}/clarification-status                   │
│  WebSocket /ws/{id}                                             │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│              WorkflowOrchestrator (orchestrator.py)             │
│                                                                  │
│  ✓ Manages query parsing                                        │
│  ✓ Detects incomplete inputs                                    │
│  ✓ Sends clarification questions                                │
│  ✓ Handles user responses                                       │
│  ✓ Manages workflow states                                      │
└─────────┬──────────────────────────────────────────────────┬────┘
          │                                                  │
    ┌─────▼─────────┐                          ┌────────────▼──────┐
    │ PlannerAgent  │                          │ ExtractionAgent    │
    │ (NEW LOGIC)   │                          │ & AnalysisAgent    │
    │               │                          │                    │
    │ ✓ Extracts    │                          │ ✓ Fetches flights  │
    │   cities      │                          │ ✓ Analyzes results │
    │ ✓ Extracts    │                          │                    │
    │   dates       │                          │                    │
    │ ✓ Generates   │                          │                    │
    │   clarify     │                          │                    │
    │   questions   │                          │                    │
    └──────┬────────┘                          └────────────┬───────┘
           │                                                │
    ┌──────▼────────────────────────────┐                  │
    │    Clarification Questions         │                  │
    │                                    │                  │
    │ Type: origin                       │                  │
    │ Question: "Which city from?"       │                  │
    │ Examples: [DEL, MUM, HYD, ...]     │                  │
    │                                    │                  │
    │ Type: destination                  │                  │
    │ Question: "To which city?"         │                  │
    │ Examples: [DEL, MUM, BLR, ...]     │                  │
    │                                    │                  │
    │ Type: date                         │                  │
    │ Question: "When to travel?"        │                  │
    │ Examples: [tomorrow, next Monday]  │                  │
    └────────────────────────────────────┘                  │
                                                             │
                                          ┌──────────────────▼───┐
                                          │  Flight Results       │
                                          │                       │
                                          │ ✓ List of flights    │
                                          │ ✓ AI analysis        │
                                          │ ✓ Top 3 picks        │
                                          │ ✓ Stored in DB       │
                                          └───────────────────────┘
```

## Complete Workflow State Machine

```
                        ┌─────────────────────────────┐
                        │    User Starts Search       │
                        └──────────────┬──────────────┘
                                       │
                                       ▼
                        ┌──────────────────────────────┐
                        │  PLANNING                    │
                        │  Parse query for all fields  │
                        └──────────────┬───────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    │                                     │
                    ▼                                     ▼
        ┌──────────────────────────┐      ┌────────────────────────────┐
        │   Complete ✅            │      │   Incomplete ❌            │
        │  (has origin & dest)     │      │  (missing fields)          │
        │                          │      │                            │
        └──────────────┬───────────┘      └────────────┬───────────────┘
                       │                                │
                       │                                ▼
                       │                   ┌─────────────────────────┐
                       │                   │AWAITING_CLARIFICATION   │
                       │                   │Send questions           │
                       │                   │Wait for response        │
                       │                   └────────────┬────────────┘
                       │                                │
                       │                     User typed: response
                       │                                │
                       │                                ▼
                       │                   ┌─────────────────────────┐
                       │                   │ Combine & Re-parse      │
                       │                   │ original + clarification│
                       │                   └────────────┬────────────┘
                       │                                │
                       │                    ┌───────────┴────────────┐
                       │                    │                        │
                       │                    ▼                        ▼
                       │          ┌──────────────────┐   ┌─────────────────┐
                       │          │   Complete ✅   │   │ Still missing ❌ │
                       │          │ → Continue      │   │ Ask again       │
                       │          └────────┐─────────┘   └────────┬────────┘
                       │                   │                      │
                       └───────────────────┼──────────────────────┘
                                           │
                                           ▼
                        ┌───────────────────────────────┐
                        │  EXTRACTING                   │
                        │  Get flights from APIs        │
                        │  or use demo data             │
                        └───────────────────┬───────────┘
                                            │
                                            ▼
                        ┌───────────────────────────────┐
                        │  ANALYZING                    │
                        │  AI analysis with Groq        │
                        │  Find top 3 recommendations   │
                        └───────────────────┬───────────┘
                                            │
                                            ▼
                        ┌───────────────────────────────┐
                        │  COMPLETED ✅                 │
                        │  Return results to user       │
                        │  Save to history              │
                        └───────────────────────────────┘
```

## Query Processing Flow

```
User Input: "I need a flight to Delhi"
    │
    ▼
┌────────────────────────────────────────┐
│ PlannerAgent.parse_query()             │
│                                        │
│ Extract origin  → NOT FOUND ❌         │
│ Extract destination → "Delhi" ✅       │
│ Extract date → DEFAULT (tomorrow) ✅   │
│                                        │
│ Result: valid=False                    │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│ Generate clarification questions:       │
│                                        │
│ 1. "Which city are you flying from?"  │
│    Examples: Hyderabad, Mumbai, etc.   │
│                                        │
│ 2. (destination already has example)   │
│    Skip if already provided            │
│                                        │
│ 3. (date already extracted)            │
│    Skip if already extracted           │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│ Send WebSocket: type="clarification"   │
│ with questions & examples              │
└────────────────────────────────────────┘
    │
    ▼ (User provides answer)

User Response: "from Hyderabad tomorrow"
    │
    ▼
┌────────────────────────────────────────┐
│ POST /api/workflow/{id}/clarify        │
│                                        │
│ Combine queries:                       │
│ source = "I need a flight to Delhi"   │
│ response = "from Hyderabad tomorrow"  │
│ combined = source + " " + response    │
└────────────────────────────────────────┘
    │
    ▼
┌────────────────────────────────────────┐
│ Re-parse combined query:               │
│ "I need a flight to Delhi from        │
│  Hyderabad tomorrow"                  │
│                                        │
│ Extract origin     → "Hyderabad" ✅   │
│ Extract destination → "Delhi" ✅      │
│ Extract date       → "tomorrow" ✅     │
│                                        │
│ Result: valid=True → Continue workflow │
└────────────────────────────────────────┘
    │
    ▼
Extract Flights → Analyze → Complete ✅
```

## Clarification Question Format

```json
{
  "type": "clarification",
  "payload": {
    "questions": [
      {
        "type": "origin",
        "question": "Which city are you flying from? (e.g., Hyderabad, Delhi, Mumbai, Bangalore, etc.)",
        "examples": ["Delhi", "Mumbai", "Hyderabad", "Bangalore", "Kolkata"]
      },
      {
        "type": "destination", 
        "question": "Which city would you like to travel to? (e.g., Delhi, Mumbai, Bangalore, Goa, etc.)",
        "examples": ["Delhi", "Mumbai", "Bangalore", "Goa", "Chennai"]
      },
      {
        "type": "date",
        "question": "When do you want to travel? (e.g., tomorrow, 15 May, next Monday, etc.)",
        "examples": ["tomorrow", "day after tomorrow", "15 May", "next Monday"]
      }
    ],
    "timestamp": "2026-04-28T00:24:03.123Z"
  }
}
```

## Decision Tree: Complete or Incomplete?

```
                    ┌─ Origin found? ─┐
                    │                 │
                 YES│                 │NO
                    │                 │
                    ▼                 ▼
            ┌──────────────┐   ┌──────────────┐
            │ Has Origin ✅│   │Missing Origin│
            └──────┬───────┘   └────────┬─────┘
                   │                    │
                   ▼                    ▼
          ┌──────────────┐   Ask: "From where?"
          │Destination?  │
          └──────┬───────┘
                 │
              YES│                 NO
                 │                 │
                 ▼                 ▼
         ┌──────────────┐   ┌──────────────┐
         │ Has Dest ✅  │   │Missing Dest  │
         └──────┬───────┘   └────────┬─────┘
                │                    │
                ▼                    ▼
        ┌──────────────┐   Ask: "To where?"
        │   Date? (*)  │
        └──────┬───────┘
               │
         (*) = Date is optional,
               defaults to tomorrow
               │
               ▼
        ┌──────────────┐
        │ COMPLETE ✅  │
        │ Can proceed  │
        └──────────────┘
```

## Response Handling Logic

```
User provides clarification response:
    │
    ▼
┌──────────────────────────────────────────┐
│ Check if workflow is awaiting            │
│ clarification                            │
└─────────────────┬──────────────────────┬─┘
                  │                      │
               YES│                      │NO
                  │                      │
                  ▼                      ▼
         ┌─────────────────┐   ┌─────────────────┐
         │ Process response│   │ Error 400:      │
         └────────┬────────┘   │ Not awaiting    │
                  │            │ clarification   │
                  ▼            └─────────────────┘
         ┌─────────────────┐
         │ Combine queries │
         │ and re-parse    │
         └────────┬────────┘
                  │
          ┌───────┴────────────┐
          │                    │
      VALID✅                INVALID❌
          │                    │
          ▼                    ▼
    ┌─────────────┐   ┌──────────────────┐
    │State:       │   │Still asking for  │
    │EXTRACTING   │   │more information  │
    │Continue...  │   │Send new questions│
    └─────────────┘   └──────────────────┘
```

## Files Changed Summary

```
┌─ backend/
│  ├─ agents/
│  │  ├─ planner_agent.py (42 lines changed)
│  │  │  ├─ NEW: _generate_clarification_questions()
│  │  │  └─ MOD: parse_query() adds clarification_questions
│  │  │
│  │  └─ workflow_orchestrator.py (192 lines changed)
│  │     ├─ NEW: provide_clarification()
│  │     ├─ NEW: _continue_workflow()
│  │     ├─ ADD: _original_query, _awaiting_clarification
│  │     └─ MOD: run() detects incomplete queries
│  │
│  ├─ api/
│  │  └─ models.py (1 line changed)
│  │     └─ ADD: AWAITING_CLARIFICATION stage
│  │
│  ├─ utils/
│  │  └─ connection_manager.py (10 lines changed)
│  │     └─ NEW: send_clarification_questions()
│  │
│  └─ main.py (37 lines changed)
│     ├─ NEW: POST /api/workflow/{id}/clarify
│     └─ NEW: GET /api/workflow/{id}/clarification-status
│
└─ Test Files
   └─ test_incomplete_inputs.py (NEW)
      ├─ Tests incomplete queries
      ├─ Tests complete queries
      └─ Tests clarification flow
```

This implementation provides a seamless, conversational experience for users while maintaining the system's ability to handle complete queries immediately.
