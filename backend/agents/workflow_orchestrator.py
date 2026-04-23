"""
Workflow Orchestrator
Coordinates all agents in the correct sequence.
Manages workflow state, error recovery, and user interaction points.
"""

import asyncio
from typing import Optional
from datetime import datetime

from agents.planner_agent import PlannerAgent
from agents.browser_agent import BrowserAgent
from agents.vision_agent import VisionAgent
from agents.extraction_agent import ExtractionAgent
from agents.form_filling_agent import FormFillingAgent
from api.models import WorkflowStage, PassengerDetails
from utils.connection_manager import ConnectionManager
from utils.logger import AgentLogger


class WorkflowOrchestrator:
    """
    Orchestrates the full agentic workflow:
    Plan → Browse → Extract → Present → Fill → Stop
    """

    def __init__(self, workflow_id: str, connection_manager: ConnectionManager):
        self.workflow_id = workflow_id
        self.manager = connection_manager
        self.logger = AgentLogger("orchestrator")
        
        # Agents
        self.planner = PlannerAgent()
        self.browser: Optional[BrowserAgent] = None
        self.vision = VisionAgent()
        self.extractor = ExtractionAgent()
        self.form_filler = FormFillingAgent()
        
        # State
        self.stage = WorkflowStage.IDLE
        self.flights = []
        self.plan = None
        self.logs = []
        self._running = False
        self._error = None
        self._passenger_event = asyncio.Event()
        self._passenger_details: Optional[PassengerDetails] = None
        self._selected_flight_index: Optional[int] = None
        self._flight_selected_event = asyncio.Event()

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
            
            # ── Step 2: Launch Browser ────────────────────────────────────────
            await self._set_stage(WorkflowStage.OPENING_BROWSER, "Launching visible browser...")
            
            self.browser = BrowserAgent(
                on_screenshot=self._on_screenshot,
                on_log=self._make_browser_log_handler(),
            )
            await self.browser.launch()
            await self._log("success", "browser", "Browser launched in visible mode")
            
            # ── Step 3: Navigate to MakeMyTrip ───────────────────────────────
            await self._set_stage(WorkflowStage.NAVIGATING, "Opening MakeMyTrip...")
            
            # Go directly to Flights surface; the generic homepage frequently A/B tests away
            # the flight search widget and breaks selectors.
            await self.browser.navigate("https://www.makemytrip.com/flights/")
            await self._log("info", "browser", "MakeMyTrip homepage loaded")
            
            # ── Step 4: Handle Popups ─────────────────────────────────────────
            await self._log("info", "browser", "Checking for popups and overlays...")
            await self.browser.close_popups()
            
            # Free DOM-based popup check (no API key needed)
            popup_check = await self.vision.detect_popup(self.browser.page)
            if popup_check.get("has_popup"):
                await self._log("info", "vision",
                    f"DOM detected popup: {popup_check.get('popup_type')}")
                await self.browser.close_popups()
            
            # ── Step 5: Search Flights ────────────────────────────────────────
            await self._set_stage(WorkflowStage.SEARCHING, "Configuring flight search...")
            
            await self.browser.click_one_way()
            await asyncio.sleep(0.5)
            
            await self._log("info", "browser", f"Entering origin: {origin['display']}")
            await self.browser.fill_origin(origin["display"])
            await asyncio.sleep(0.8)
            
            await self._log("info", "browser", f"Entering destination: {destination['display']}")
            await self.browser.fill_destination(destination["display"])
            await asyncio.sleep(0.8)
            
            await self._log("info", "browser", f"Selecting date: {date}")
            await self.browser.fill_date(date)
            await asyncio.sleep(0.5)
            
            await self._log("info", "browser", "Clicking Search Flights...")
            await self.browser.click_search()
            # Results page is often SPA-driven; wait for URL transition to reduce "stuck after search".
            try:
                await self.browser.page.wait_for_url("**/flight/search**", timeout=60000)
            except Exception:
                pass
            try:
                await self.browser.page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            await asyncio.sleep(1.0)
            
            # ── Step 6: Wait for Results ──────────────────────────────────────
            await self._set_stage(WorkflowStage.SEARCHING, "Waiting for flight results...")
            
            loaded = await self.browser.wait_for_results()
            
            if not loaded:
                await self._log("warning", "browser", "Results may not have fully loaded")
                # Free DOM page-state analysis (no API key)
                state = await self.vision.analyze_page_state(self.browser.page)
                await self._log("info", "vision",
                    f"Page state: {state.get('page_type')} -> {state.get('suggested_action')}")

                # If search form submission produced an unstable/blank results state,
                # recover by navigating directly to a deterministic results URL.
                await self._log(
                    "info",
                    "browser",
                    "Attempting direct results navigation fallback...",
                )
                recovered = await self.browser.navigate_results_direct(
                    origin["code"],
                    destination["code"],
                    date,
                )
                if recovered:
                    loaded = await self.browser.wait_for_results()
                    if loaded:
                        await self._log(
                            "success",
                            "browser",
                            "Recovered search via direct results URL",
                        )
            
            # ── Step 7: Extract Flight Data ────────────────────────────────────
            await self._set_stage(WorkflowStage.EXTRACTING, "Extracting flight data...")

            # First try robust live-DOM card text extraction.
            dom_cards = await self.browser.extract_flights_from_dom(max_cards=25)
            if dom_cards:
                parsed_dom_flights = self.vision.parse_card_texts(dom_cards)
                if parsed_dom_flights:
                    self.flights = parsed_dom_flights
                    await self._log(
                        "success",
                        "extraction",
                        f"Extracted {len(self.flights)} flights from live DOM cards",
                    )

            html = await self.browser.get_page_html()
            if not self.flights:
                self.flights = self.extractor.extract_flights(html)
            
            # Free DOM fallback if HTML extraction missed flights
            if not self.flights:
                await self._log("info", "vision", "Trying DOM card extraction as fallback...")
                vision_result = await self.vision.extract_flight_data_from_screenshot(self.browser.page)
                if vision_result.get("flights"):
                    self.flights = vision_result["flights"]
                    await self._log("info", "vision",
                        f"DOM vision extracted {len(self.flights)} flights")
            
            if self.flights:
                await self._log("success", "extraction", 
                    f"Extracted {len(self.flights)} flights successfully")
                await self.manager.send_flights(self.workflow_id, self.flights)
            else:
                await self._log("warning", "extraction", 
                    "Could not extract flight data. The page may have changed.")
                # Send mock data for demonstration
                self.flights = self._generate_demo_flights(
                    origin["display"], destination["display"], date
                )
                await self._log("info", "extraction", 
                    f"Using {len(self.flights)} demo flights for demonstration")
                await self.manager.send_flights(self.workflow_id, self.flights)
            
            # ── Step 8: Await User Flight Selection ────────────────────────────
            await self._set_stage(WorkflowStage.AWAITING_SELECTION, 
                "Flights extracted. Please select a flight from the list.")
            
            await self._log("info", "orchestrator", 
                "Waiting for user to select a flight...")
            
            try:
                # Don't let the UI feel "stuck" forever if selection is missed.
                await asyncio.wait_for(self._flight_selected_event.wait(), timeout=60.0)
            except asyncio.TimeoutError:
                if self.flights:
                    self._selected_flight_index = 0
                    await self._log(
                        "warning",
                        "orchestrator",
                        "No flight selected in time — auto-selecting the first flight to continue",
                        {"auto_selected_index": 0},
                    )
                else:
                    await self._log("warning", "orchestrator", "Flight selection timed out")
                    await self._set_stage(WorkflowStage.ERROR, "No flight selected within 60 seconds")
                    return
            
            if self._selected_flight_index is not None:
                await self._log("info", "browser", 
                    f"Clicking flight #{self._selected_flight_index + 1}...")
                await self.browser.click_flight_at_index(self._selected_flight_index)
                await asyncio.sleep(2.0)
            
            # ── Step 9: Await Passenger Details ────────────────────────────────
            await self._set_stage(WorkflowStage.FILLING_FORM, 
                "Waiting for passenger details...")
            
            await self._log("info", "orchestrator", "Waiting for passenger details...")
            
            try:
                await asyncio.wait_for(self._passenger_event.wait(), timeout=300.0)
            except asyncio.TimeoutError:
                await self._log("warning", "orchestrator", "Passenger details timed out")
                await self._set_stage(WorkflowStage.ERROR, "No passenger details within 5 minutes")
                return
            
            # ── Step 10: Fill Passenger Form ───────────────────────────────────
            if self._passenger_details:
                passenger_dict = self._passenger_details.model_dump()
                await self._log("info", "form_filling", 
                    f"Filling details for {passenger_dict['first_name']} {passenger_dict['last_name']}")

                # Check for payment page
                try:
                    result = await asyncio.wait_for(
                        self.form_filler.fill_and_detect_payment(
                            self.browser, passenger_dict
                        ),
                        timeout=120.0,
                    )
                except asyncio.TimeoutError:
                    await self._log(
                        "error",
                        "form_filling",
                        "Passenger form filling timed out before completion",
                    )
                    await self._set_stage(
                        WorkflowStage.ERROR,
                        "Passenger form filling timed out. Please retry with a new search.",
                    )
                    return
                
                if result.get("stopped_before_payment"):
                    await self._log("success", "orchestrator", 
                        "STOPPING: Payment page detected. Workflow complete!")
                    await self._set_stage(
                        WorkflowStage.STOPPED_BEFORE_PAYMENT,
                        "Stopped before payment page as instructed. Booking form is ready."
                    )
                else:
                    await self._log("success", "form_filling", "Passenger form filled")
                    await self._set_stage(
                        WorkflowStage.STOPPED_BEFORE_PAYMENT,
                        "Passenger details filled. Ready to proceed (payment not executed)."
                    )
            
        except asyncio.CancelledError:
            await self._log("info", "orchestrator", "Workflow cancelled")
        except Exception as e:
            self._error = str(e)
            self.logger.error(f"Workflow error: {e}")
            await self._log("error", "orchestrator", f"Workflow error: {str(e)}")
            await self._set_stage(WorkflowStage.ERROR, str(e))
        finally:
            self._running = False
            # Avoid leaking browsers/contexts when the workflow ends naturally.
            try:
                if self.browser:
                    await self.browser.close()
            except Exception:
                pass

    async def set_passenger_details(self, passenger: PassengerDetails):
        """Receive passenger details from user"""
        self._passenger_details = passenger
        self._passenger_event.set()

    async def select_flight(self, flight_index: int):
        """Receive flight selection from user"""
        self._selected_flight_index = flight_index
        self._flight_selected_event.set()

    async def stop(self):
        """Stop the workflow and close the browser"""
        self._running = False
        if self.browser:
            await self.browser.close()

    def get_status(self) -> dict:
        """Get current workflow status"""
        return {
            "workflow_id": self.workflow_id,
            "stage": self.stage,
            "logs": self.logs[-50:],
            "flights": self.flights,
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

    async def _on_screenshot(self, screenshot_bytes: bytes):
        """Handle screenshot from browser agent"""
        await self.manager.send_screenshot(self.workflow_id, screenshot_bytes)

    def _make_browser_log_handler(self):
        """Create a log callback for the browser agent"""
        async def handler(level: str, message: str, details: dict = None):
            await self._log(level, "browser", message, details)
        return handler

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
        
        for i, (airline_name, code) in enumerate(airlines[:6]):
            dep_h = dep_hours[i]
            dep_m = random.choice([0, 10, 20, 30, 40, 50])
            duration_mins = random.randint(60, 180)
            arr_h = (dep_h + duration_mins // 60) % 24
            arr_m = (dep_m + duration_mins % 60) % 60
            
            flight_num = f"{code}{random.randint(100, 999)}"
            dur_h = duration_mins // 60
            dur_m = duration_mins % 60
            
            price = base_price + random.randint(-1500, 3000)
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
