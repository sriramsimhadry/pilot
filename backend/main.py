"""
Agentic AI Workflow for Aeroplanes - FastAPI Backend
Multi-agent system for automated flight search on MakeMyTrip
"""

import asyncio
import json
import uuid
from datetime import datetime

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from agents.workflow_orchestrator import WorkflowOrchestrator
from api.models import (
    QueryRequest,
    PassengerDetails,
)
from utils.logger import AgentLogger
from utils.connection_manager import ConnectionManager

app = FastAPI(
    title="Agentic AI Workflow for Aeroplanes",
    description="Multi-agent system for automated flight search",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

manager = ConnectionManager()
active_workflows: dict[str, WorkflowOrchestrator] = {}
logger = AgentLogger("main")


@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.post("/api/workflow/start")
async def start_workflow(request: QueryRequest):
    """Start a new flight search workflow"""
    workflow_id = str(uuid.uuid4())

    orchestrator = WorkflowOrchestrator(
        workflow_id=workflow_id,
        connection_manager=manager,
    )
    active_workflows[workflow_id] = orchestrator

    task = asyncio.create_task(orchestrator.run(query=request.query))

    # Ensure finished workflows don't linger and later emit timeouts/errors.
    def _cleanup(_task: asyncio.Task):
        active_workflows.pop(workflow_id, None)

    task.add_done_callback(_cleanup)

    return {"workflow_id": workflow_id, "status": "started"}


@app.post("/api/workflow/{workflow_id}/passenger")
async def submit_passenger(workflow_id: str, passenger: PassengerDetails):
    """Submit passenger details to an active workflow"""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    orchestrator = active_workflows[workflow_id]
    await orchestrator.set_passenger_details(passenger)
    return {"status": "passenger_details_received"}


@app.post("/api/workflow/{workflow_id}/select-flight")
async def select_flight(workflow_id: str, flight_index: int):
    """Select a flight from the extracted results"""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    orchestrator = active_workflows[workflow_id]
    await orchestrator.select_flight(flight_index)
    return {"status": "flight_selected"}


@app.post("/api/workflow/{workflow_id}/stop")
async def stop_workflow(workflow_id: str):
    """Stop an active workflow"""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    orchestrator = active_workflows[workflow_id]
    await orchestrator.stop()
    del active_workflows[workflow_id]
    return {"status": "stopped"}


@app.get("/api/workflow/{workflow_id}/status")
async def get_status(workflow_id: str):
    """Get the current status of a workflow"""
    if workflow_id not in active_workflows:
        raise HTTPException(status_code=404, detail="Workflow not found")

    orchestrator = active_workflows[workflow_id]
    return orchestrator.get_status()


@app.websocket("/ws/{workflow_id}")
async def websocket_endpoint(websocket: WebSocket, workflow_id: str):
    """WebSocket endpoint for real-time updates"""
    await manager.connect(websocket, workflow_id)
    # On reconnect/refresh, immediately replay current state so the UI doesn't appear stuck.
    try:
        if workflow_id in active_workflows:
            orch = active_workflows[workflow_id]
            status = orch.get_status()
            # Stage
            try:
                await manager.send_stage_update(
                    workflow_id,
                    status.get("stage"),
                    "",
                )
            except Exception:
                pass
            # Plan + flights (if already available)
            try:
                if status.get("flights") is not None:
                    await manager.send_flights(workflow_id, status.get("flights"))
            except Exception:
                pass
            try:
                if getattr(orch, "plan", None):
                    await manager.send_plan(workflow_id, orch.plan)
            except Exception:
                pass
    except Exception as e:
        logger.error(f"WebSocket snapshot error: {e}")
    try:
        while True:
            data = await websocket.receive_text()
            msg = json.loads(data)
            
            if msg.get("type") == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, workflow_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, workflow_id)
