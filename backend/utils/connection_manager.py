"""WebSocket connection manager for real-time updates"""

import json
import base64
from typing import Dict, List, Optional
from fastapi import WebSocket
from datetime import datetime


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, workflow_id: str):
        await websocket.accept()
        if workflow_id not in self.active_connections:
            self.active_connections[workflow_id] = []
        self.active_connections[workflow_id].append(websocket)

    def disconnect(self, websocket: WebSocket, workflow_id: str):
        if workflow_id in self.active_connections:
            try:
                self.active_connections[workflow_id].remove(websocket)
            except ValueError:
                pass
            if not self.active_connections[workflow_id]:
                self.active_connections.pop(workflow_id, None)

    async def send_message(self, workflow_id: str, message: dict):
        """Send a JSON message to all connections for a workflow"""
        if workflow_id not in self.active_connections:
            return

        dead = []
        for ws in self.active_connections[workflow_id]:
            try:
                await ws.send_text(json.dumps(message))
            except Exception:
                dead.append(ws)

        for ws in dead:
            self.disconnect(ws, workflow_id)

    async def send_log(
        self,
        workflow_id: str,
        agent: str,
        level: str,
        message: str,
        details: Optional[dict] = None,
    ):
        """Send a log entry to frontend"""
        await self.send_message(workflow_id, {
            "type": "log",
            "payload": {
                "timestamp": datetime.utcnow().isoformat(),
                "agent": agent,
                "level": level,
                "message": message,
                "details": details or {},
            }
        })

    async def send_screenshot(self, workflow_id: str, screenshot_bytes: bytes):
        """Send a base64-encoded screenshot to frontend"""
        b64 = base64.b64encode(screenshot_bytes).decode("utf-8")
        await self.send_message(workflow_id, {
            "type": "screenshot",
            "payload": {
                "data": b64,
                "timestamp": datetime.utcnow().isoformat(),
            }
        })

    async def send_flights(self, workflow_id: str, flights: list):
        """Send extracted flight data to frontend"""
        await self.send_message(workflow_id, {
            "type": "flights",
            "payload": flights,
        })

    async def send_summary(self, workflow_id: str, summary: str):
        """Send LLM summary to frontend"""
        await self.send_message(workflow_id, {
            "type": "summary",
            "payload": summary,
        })

    async def send_stage_update(
        self, workflow_id: str, stage: str, message: str = ""
    ):
        """Send workflow stage update"""
        await self.send_message(workflow_id, {
            "type": "stage",
            "payload": {
                "stage": stage,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            }
        })

    async def send_plan(self, workflow_id: str, plan: dict):
        """Send the generated plan to frontend"""
        await self.send_message(workflow_id, {
            "type": "plan",
            "payload": plan,
        })

    async def send_error(
        self, workflow_id: str, error: str, agent: str = "system"
    ):
        """Send error message to frontend"""
        await self.send_message(workflow_id, {
            "type": "error",
            "payload": {
                "error": error,
                "agent": agent,
                "timestamp": datetime.utcnow().isoformat(),
            }
        })

    async def send_clarification_questions(self, workflow_id: str, questions: list):
        """Send clarification questions to frontend"""
        await self.send_message(workflow_id, {
            "type": "clarification",
            "payload": {
                "questions": questions,
                "timestamp": datetime.utcnow().isoformat(),
            }
        })
