# Aeroo Flight Search - Interactive Query Clarification Implementation

## Overview
The Aeroo application now supports interactive query clarification for incomplete flight search inputs. When users provide incomplete information (missing origin, destination, or date), the system asks clarifying questions instead of returning errors.

## What Was Implemented

### 1. **PlannerAgent Enhancement** (`backend/agents/planner_agent.py`)
- Added `_generate_clarification_questions()` method that identifies missing fields and creates helpful prompts
- Modified `parse_query()` to:
  - Return `valid: False` with `clarification_questions` list for incomplete queries
  - Return `complete: True/False` to track if minimum required fields are present
  - Include specific, actionable questions with examples for each missing field

### 2. **WorkflowOrchestrator Updates** (`backend/agents/workflow_orchestrator.py`)
- Added `_original_query` storage to maintain initial query context
- Added `_awaiting_clarification` state flag
- Added `provide_clarification()` method to handle user responses
- Added `_continue_workflow()` method to avoid code duplication
- Modified `run()` method to:
  - Store original query
  - Detect when clarification is needed
  - Send clarification questions via WebSocket
  - Transition to `AWAITING_CLARIFICATION` stage instead of ERROR

### 3. **API Models Update** (`backend/api/models.py`)
- Added `AWAITING_CLARIFICATION` stage to `WorkflowStage` enum
- Allows frontend to display clarification UI

### 4. **Connection Manager Extension** (`backend/utils/connection_manager.py`)
- Added `send_clarification_questions()` method to broadcast questions to frontend via WebSocket
- Enables real-time question delivery with timestamp

### 5. **API Endpoints** (`backend/main.py`)
Added two new endpoints:

#### POST `/api/workflow/{workflow_id}/clarify`
Sends user's clarification response to continue workflow
```json
Request: { "query": "from Hyderabad tomorrow" }
Response: { "status": "clarification_received", "workflow_id": "..." }
```

#### GET `/api/workflow/{workflow_id}/clarification-status`
Checks current clarification status
```json
Response: {
  "workflow_id": "...",
  "awaiting_clarification": true/false,
  "stage": "awaiting_clarification",
  "pending_questions": [...]
}
```

## Workflow Behavior

### Complete Input Flow
```
User Input: "from Hyderabad to Delhi tomorrow"
     ↓
Parse Query (all fields found)
     ↓
Search Flights
     ↓
Analyze Results
     ↓
Complete ✅
```

### Incomplete Input Flow
```
User Input: "flight to Delhi"
     ↓
Parse Query (missing origin)
     ↓
Generate Clarification Questions
     ↓
Send to Frontend (WebSocket: type="clarification")
     ↓
AWAITING_CLARIFICATION Stage
     ↓
User Responds: "from Hyderabad tomorrow"
     ↓
POST /api/workflow/{id}/clarify
     ↓
Combine: "flight to Delhi from Hyderabad tomorrow"
     ↓
Re-parse (all fields now found)
     ↓
Search Flights
     ↓
Complete ✅
```

## Example Clarification Questions

For incomplete query: `"I need a flight to Delhi"`

System asks:
1. "Which city are you flying from? (e.g., Hyderabad, Delhi, Mumbai, Bangalore, etc.)"
   - Examples: Hyderabad, Mumbai, Bangalore
2. "Which city would you like to travel to? (e.g., Delhi, Mumbai, Bangalore, Goa, etc.)"
   - Examples: Delhi, Mumbai, Goa
3. "When do you want to travel? (e.g., tomorrow, 15 May, next Monday, etc.)"
   - Examples: tomorrow, day after tomorrow, 15 May

## Test Results

### Incomplete Queries (Properly Ask for Clarification)
✅ "flight to Delhi" → 3 clarification questions
✅ "from Hyderabad" → 3 clarification questions
✅ "Bangalore" → 3 clarification questions

### Complete Queries (Work Immediately)
✅ "I want to fly from Hyderabad to Delhi tomorrow" → Direct search
✅ "from Mumbai to Bangalore on 15th May" → Direct search
✅ "Delhi to Goa next Friday" → Direct search
✅ "from Pune to Jaipur today" → Direct search
✅ "Hyderabad → Chennai on 20/05/2025" → Direct search

### Clarification Flow
✅ Initial: "I need a flight to Delhi" (incomplete)
✅ Clarify: "from Hyderabad tomorrow"
✅ Combined: "I need a flight to Delhi from Hyderabad tomorrow" (complete)

## Frontend Integration

### WebSocket Message Format

**When clarification needed:**
```json
{
  "type": "clarification",
  "payload": {
    "questions": [
      {
        "type": "origin",
        "question": "Which city are you flying from?",
        "examples": ["Hyderabad", "Delhi", "Mumbai"]
      },
      ...
    ],
    "timestamp": "2026-04-28T..."
  }
}
```

**Send clarification back:**
```
POST /api/workflow/{workflow_id}/clarify
{
  "query": "from Hyderabad tomorrow"
}
```

## Key Features

✨ **Intelligent Questions**: Only asks for missing information
✨ **Helpful Examples**: Provides relevant suggestions for each field
✨ **Context Preservation**: Combines original query with clarifications
✨ **Real-time Updates**: Uses WebSocket for immediate feedback
✨ **State Management**: Tracks clarification state to prevent errors
✨ **Fallback**: If clarification doesn't complete query, asks again
✨ **Multi-step Support**: Handles multiple rounds of clarification

## Files Modified

1. `backend/agents/planner_agent.py` - Query parsing enhancement
2. `backend/agents/workflow_orchestrator.py` - Clarification handling
3. `backend/api/models.py` - Added AWAITING_CLARIFICATION stage
4. `backend/utils/connection_manager.py` - WebSocket message support
5. `backend/main.py` - New API endpoints

## Testing

Run the test script to verify:
```bash
python test_incomplete_inputs.py
```

Output shows:
- Incomplete queries properly identified with clarification questions
- Complete queries processed immediately
- Clarification flow combining queries correctly
