# Clarification Flow - Complete Implementation Guide

## Problem Fixed

The Aeroo flight booking system had a **syntax error in ChatPanel.jsx** that prevented the clarification flow from working. The error was in the `handleSubmit` function with duplicate/broken code:

```javascript
// BEFORE (broken):
const handleSubmit = (e) => {
    e.preventDefault()
    if (!canSearch) return
    if (awaitingClarification) {
      sendClarification(query.trim())
    } else {
      startWorkflow(query.trim())
    }
    setQuery('')
  }
  e.preventDefault()          // ← DUPLICATE/BROKEN
  if (!canSearch) return
  startWorkflow(query.trim())
  setQuery('')
}

// AFTER (fixed):
const handleSubmit = (e) => {
    e.preventDefault()
    if (!canSearch) return
    if (awaitingClarification) {
      sendClarification(query.trim())
    } else {
      startWorkflow(query.trim())
    }
    setQuery('')
  }
```

## How Clarification Flow Works

### 1. User Sends Incomplete Query
```
User: "i want to go to delhi"
```

### 2. Backend Parses and Detects Incomplete Query
- **PlannerAgent** parses the query
- Extracts: destination=Delhi, origin=None
- Since origin is missing, query is marked as **invalid**
- Generates clarification questions:
  ```
  - Q1: Which city are you flying from?
    Examples: [cities...]
  - Q2: When do you want to travel?
    Examples: ["tomorrow", "15 May", "next Monday", ...]
  ```

### 3. Backend Sends to Frontend
- **WorkflowOrchestrator** sends:
  - Stage: `AWAITING_CLARIFICATION`
  - Message: "I need some more details to search for flights"
  - Clarification questions (via WebSocket)

### 4. Frontend Displays Questions
**In ChatPanel.jsx:**
```jsx
{entry.clarificationQuestions && entry.clarificationQuestions.length > 0 && (
  <div className={styles.messageRowBot}>
    <div className={styles.clarificationBubble}>
      {entry.clarificationQuestions.map((q, i) => (
        <div key={i} className={styles.clarificationQuestion}>
          <div>{q.question}</div>
          {q.examples && q.examples.length > 0 && (
            <div className={styles.clarificationChips}>
              {q.examples.map((ex, eIdx) => (
                <button
                  key={eIdx}
                  className={styles.clarificationChip}
                  onClick={() => {
                    setQuery(ex)
                    inputRef.current?.focus()
                  }}
                >{ex}</button>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  </div>
)}
```

**Input field changes placeholder:**
```jsx
placeholder={
  awaitingClarification ? 'Answer the question…' :
    'Type or speak your flight request…'
}
```

### 5. User Provides Clarification
User can either:
- **Click an example**: Automatically fills the input
- **Type a custom answer**: "from Hyderabad tomorrow"

### 6. Form Submission (NOW FIXED)
When user clicks the submit button:
```javascript
const handleSubmit = (e) => {
  e.preventDefault()
  if (!canSearch) return
  if (awaitingClarification) {
    sendClarification(query.trim())  // ← Sends to backend
  } else {
    startWorkflow(query.trim())
  }
  setQuery('')
}
```

### 7. Backend Processes Clarification
**In useStore.js:**
```javascript
sendClarification: async (text) => {
  const { workflowId } = get()
  if (!workflowId || !text.trim()) return

  get()._updateCurrentHistory({
    clarificationReply: text.trim(),
  })

  set({ awaitingClarification: false, clarificationQuestions: [] })

  try {
    await fetch(`${API_BASE}/api/workflow/${workflowId}/clarify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query: text.trim() }),
    })
  } catch (err) {
    set({ error: err.message, isRunning: false })
    get()._updateCurrentHistory({ status: 'error' })
  }
}
```

### 8. Backend Re-parses Combined Query
**In workflow_orchestrator.py:**
```python
async def provide_clarification(self, clarification_response: str):
    # Combine original query with clarification
    combined_query = f"{self._original_query} {clarification_response}".strip()
    # Re-parse with combined query
    self.plan = self.planner.parse_query(combined_query)
    
    if not self.plan["valid"]:
        # Still need more info
        # Send more clarification questions
    else:
        # Plan is valid - proceed with workflow
        await self._continue_workflow()
```

### 9. Workflow Continues
Once clarification is valid:
1. **Extract flights** from APIs (MakeMyTrip, etc.)
2. **Analyze flights** with AI (Groq LLM)
3. **Display results** to user
4. **Stage transitions**: planning → extracting → analyzing → completed

Frontend clears clarification state when stage changes:
```javascript
if (['planning', 'extracting', 'analyzing', 'completed'].includes(msg.payload.stage)) {
  set({ awaitingClarification: false, clarificationQuestions: [] })
}
```

## Example Conversation Flow

```
USER: "i want to go to delhi"
AI:   "Which city are you flying from? [Hyderabad] [Mumbai] [Bangalore] ..."
      "When do you want to travel? [tomorrow] [15 May] [next Monday] ..."

USER: "from Mumbai" (or clicks button)
AI:   [Processing...]
      "Searching live APIs for flights..."
      [Shows 5-10 flights in results]
      [AI analysis of top 3 picks]
      
USER: Selects a flight
AI:   [Asks for passenger details]
      [Fills form]
      [Stops before payment]
```

## Files Changed

- **frontend/src/components/ChatPanel.jsx** - Fixed `handleSubmit` syntax error

## Key Components

### Backend (Python/FastAPI)
1. **PlannerAgent** (`backend/agents/planner_agent.py`)
   - Parses natural language queries
   - Generates clarification questions
   - Returns structured execution plans

2. **WorkflowOrchestrator** (`backend/agents/workflow_orchestrator.py`)
   - Manages workflow state (AWAITING_CLARIFICATION, PLANNING, EXTRACTING, etc.)
   - Handles clarification responses
   - Coordinates all agents

3. **ConnectionManager** (`backend/utils/connection_manager.py`)
   - Sends clarification questions over WebSocket
   - Real-time communication with frontend

### Frontend (React/Zustand)
1. **useStore** (`frontend/src/store/useStore.js`)
   - Manages `awaitingClarification` state
   - Handles WebSocket messages (`clarification` type)
   - Updates chat history with clarification questions
   - Calls `sendClarification()` on form submit

2. **ChatPanel** (`frontend/src/components/ChatPanel.jsx`)
   - Displays clarification questions with examples
   - Shows input field with "Answer the question…" placeholder
   - Fixed `handleSubmit` to route to `sendClarification()` when needed

## Testing Clarification

Run the test file to verify clarification detection:
```bash
python test_clarification.py
```

This will test:
- Complete queries (valid immediately)
- Incomplete queries (trigger clarification)
- Vague queries (need multiple clarifications)
- Complex queries (with passengers, class, round trip)

## Next Steps (Optional Improvements)

1. **Multi-turn clarification**: Handle cases where user needs to answer multiple questions
2. **Context awareness**: Remember common user preferences
3. **Natural language feedback**: Provide more helpful clarification prompts based on extracted partial info
4. **Form-based clarification**: For complex queries, show a modal form instead of inline questions

## Status

✅ **FIXED**: Clarification flow is now fully functional

The system correctly:
- Detects incomplete queries
- Asks clarification questions
- Receives user answers
- Re-parses combined query
- Continues with flight search
