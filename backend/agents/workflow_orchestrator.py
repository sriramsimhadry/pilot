"""
Workflow Orchestrator
Coordinates all agents in the correct sequence.
Manages workflow state, error recovery, and user interaction points.
"""

import asyncio
from typing import Optional
from datetime import datetime

from agents.planner_agent import PlannerAgent
from agents.extraction_agent import ExtractionAgent
from agents.analysis_agent import AnalysisAgent
from api.models import WorkflowStage
from utils.connection_manager import ConnectionManager
from utils.logger import AgentLogger


class WorkflowOrchestrator:
    """
    Orchestrates the chatbot flight search workflow:
    Plan -> Extract API Flights -> Analyze with LLM -> Return Results
    """

    def __init__(self, workflow_id: str, connection_manager: ConnectionManager):
        self.workflow_id = workflow_id
        self.manager = connection_manager
        self.logger = AgentLogger("orchestrator")
        
        # Agents
        self.planner = PlannerAgent()
        self.extractor = ExtractionAgent()
        self.analyzer = AnalysisAgent()
        
        # State
        self.stage = WorkflowStage.IDLE
        self.flights = []
        self.summary = None
        self.plan = None
        self.logs = []
        self._running = False
        self._error = None

    async def run(self, query: str):
        """Main workflow execution"""
        self._running = True
        
        try:
            await self._log("info", "orchestrator", f"Starting workflow for: '{query}'")
            
            # ── Step 1: Planning ──────────────────────────────────────────────
            await self._set_stage(WorkflowStage.PLANNING, "Generating execution plan...")
            
            self.plan = self.planner.parse_query(query)
            
            if not self.plan["valid"]:
                error_msg = self.plan.get("error", "Could not parse query")
                await self._log("error", "planner", error_msg)
                await self._set_stage(WorkflowStage.ERROR, error_msg)
                return
            
            parsed = self.plan["parsed"]
            origin = parsed["origin"]
            destination = parsed["destination"]
            date = parsed["date"]
            
            await self.manager.send_plan(self.workflow_id, self.plan)
            await self._log("success", "planner", 
                f"Plan created: {origin['display']} → {destination['display']} on {date}")
            
            # ── Step 2: Extract Flight Data (API FIRST) ────────────────────────
            await self._set_stage(WorkflowStage.EXTRACTING, "Searching live APIs for flights...")

            self.flights = await self.extractor.fetch_flights_from_apis(
                origin["code"], 
                destination["code"], 
                date,
                parsed.get("return_date")
            )
            
            if self.flights:
                await self._log("success", "extraction", f"Extracted {len(self.flights)} flights from live APIs")
                await self.manager.send_flights(self.workflow_id, self.flights)
            else:
                await self._log("warning", "extraction", "All APIs failed or no flights found.")
                self.flights = self._generate_demo_flights(origin["display"], destination["display"], date)
                await self._log("info", "extraction", f"Using {len(self.flights)} demo flights for demonstration")
                await self.manager.send_flights(self.workflow_id, self.flights)
            
            # ── Step 3: Analyze Flights with LLM ────────────────────────────────
            if self.flights:
                await self._set_stage(
                    WorkflowStage.ANALYZING,
                    "Analysing all flights with AI — finding top 3 picks for you..."
                )
                await self._log("info", "analysis", f"Sending {len(self.flights)} flights to Groq for analysis...")

                # Run the LLM analysis in a thread so it doesn't block the event loop
                self.summary = await asyncio.to_thread(self.analyzer.analyze_flights, self.flights)

                if self.summary:
                    top_count = len(self.summary.get("top3", [])) if isinstance(self.summary, dict) else 0
                    await self._log(
                        "success", "analysis",
                        f"AI analysis complete — {top_count} top recommendations ready" if top_count
                        else "AI analysis complete"
                    )
                    await self.manager.send_summary(self.workflow_id, self.summary)
                else:
                    await self._log("warning", "analysis", "Groq analysis skipped or returned no result")

            # ── Step 4: Complete Workflow & Save to DB ───────────────────────────────────────
            from api.db import insert_search_record
            try:
                await insert_search_record(self.workflow_id, self.plan, self.summary)
            except Exception as e:
                self.logger.error(f"Failed to save search to DB: {e}")

            await self._set_stage(WorkflowStage.COMPLETED, 
                "Flights retrieved and analyzed successfully.")
        except asyncio.CancelledError:
            await self._log("info", "orchestrator", "Workflow cancelled")
        except Exception as e:
            self._error = str(e)
            self.logger.error(f"Workflow error: {e}")
            await self._log("error", "orchestrator", f"Workflow error: {str(e)}")
            await self._set_stage(WorkflowStage.ERROR, str(e))
        finally:
            self._running = False

    async def stop(self):
        """Stop the workflow"""
        self._running = False

    def get_status(self) -> dict:
        """Get current workflow status"""
        return {
            "workflow_id": self.workflow_id,
            "stage": self.stage,
            "logs": self.logs[-50:],
            "flights": self.flights,
            "summary": self.summary,
            "error": self._error,
        }

    # ─── Private Helpers ─────────────────────────────────────────────────────

    async def _set_stage(self, stage: WorkflowStage, message: str = ""):
        """Update workflow stage and broadcast"""
        self.stage = stage
        await self.manager.send_stage_update(self.workflow_id, stage.value, message)
        self.logger.info(f"Stage: {stage.value} - {message}")

    async def _log(self, level: str, agent: str, message: str, details: dict = None):
        """Add to log and broadcast"""
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "agent": agent,
            "message": message,
            "details": details or {},
        }
        self.logs.append(entry)
        await self.manager.send_log(self.workflow_id, agent, level, message, details)

    def _generate_demo_flights(self, origin: str, destination: str, date: str) -> list:
        """Generate realistic demo flight data when extraction fails"""
        import random
        
        airlines = [
            ("IndiGo", "6E"), ("Air India", "AI"), ("SpiceJet", "SG"),
            ("Vistara", "UK"), ("Akasa Air", "QP"), ("AirAsia India", "I5"),
        ]
        
        flights = []
        base_price = random.randint(3500, 8000)
        
        dep_hours = [5, 6, 7, 8, 10, 11, 14, 16, 18, 20]
        random.shuffle(dep_hours)
        
        for i in range(20):
            airline_name, code = random.choice(airlines)
            dep_h = dep_hours[i % len(dep_hours)]
            dep_m = random.choice([0, 10, 20, 30, 40, 50])
            duration_mins = random.randint(60, 180)
            arr_h = (dep_h + duration_mins // 60) % 24
            arr_m = (dep_m + duration_mins % 60) % 60
            
            flight_num = f"{code}{random.randint(100, 999)}"
            dur_h = duration_mins // 60
            dur_m = duration_mins % 60
            
            # Add some variance to price based on airline
            airline_premium = 0 if airline_name in ["IndiGo", "SpiceJet", "AirAsia India", "Akasa Air"] else 2000
            price = base_price + airline_premium + random.randint(-1500, 3000)
            stops = "Non-stop" if random.random() > 0.4 else "1 Stop"
            
            flights.append({
                "index": i,
                "airline": airline_name,
                "flight_number": flight_num,
                "departure_time": f"{dep_h:02d}:{dep_m:02d}",
                "arrival_time": f"{arr_h:02d}:{arr_m:02d}",
                "duration": f"{dur_h}h {dur_m}m",
                "price": f"₹{price:,}",
                "stops": stops,
            })
        
        # Sort by price
        flights.sort(key=lambda x: int(x["price"].replace("₹", "").replace(",", "")))
        for i, f in enumerate(flights):
            f["index"] = i
        
        return flights
