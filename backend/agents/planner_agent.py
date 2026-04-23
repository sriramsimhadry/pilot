"""
Planner Agent — FREE version
==============================
Parses natural language flight query into a structured execution plan.

Default mode: pure Python regex — zero cost, zero API calls.
Optional upgrade: set GROQ_API_KEY in .env for free LLM-enhanced parsing.
  Groq free tier: 14,400 req/day on llama3-8b — completely free.
  Sign up at https://console.groq.com (no credit card needed).
  pip install groq
"""

import re
import json
import os
from datetime import datetime, timedelta
from typing import Optional

from utils.logger import AgentLogger

# Optional: Groq free-tier LLM for smarter query parsing
try:
    from groq import Groq as GroqClient
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False


CITIES = {
    "hyderabad": {"code": "HYD", "name": "Hyderabad", "display": "Hyderabad"},
    "hyd": {"code": "HYD", "name": "Hyderabad", "display": "Hyderabad"},
    "delhi": {"code": "DEL", "name": "Delhi", "display": "Delhi"},
    "new delhi": {"code": "DEL", "name": "Delhi", "display": "Delhi"},
    "del": {"code": "DEL", "name": "Delhi", "display": "Delhi"},
    "mumbai": {"code": "BOM", "name": "Mumbai", "display": "Mumbai"},
    "bombay": {"code": "BOM", "name": "Mumbai", "display": "Mumbai"},
    "bom": {"code": "BOM", "name": "Mumbai", "display": "Mumbai"},
    "bangalore": {"code": "BLR", "name": "Bangalore", "display": "Bangalore"},
    "bengaluru": {"code": "BLR", "name": "Bangalore", "display": "Bangalore"},
    "blr": {"code": "BLR", "name": "Bangalore", "display": "Bangalore"},
    "chennai": {"code": "MAA", "name": "Chennai", "display": "Chennai"},
    "madras": {"code": "MAA", "name": "Chennai", "display": "Chennai"},
    "kolkata": {"code": "CCU", "name": "Kolkata", "display": "Kolkata"},
    "calcutta": {"code": "CCU", "name": "Kolkata", "display": "Kolkata"},
    "pune": {"code": "PNQ", "name": "Pune", "display": "Pune"},
    "ahmedabad": {"code": "AMD", "name": "Ahmedabad", "display": "Ahmedabad"},
    "goa": {"code": "GOI", "name": "Goa", "display": "Goa"},
    "jaipur": {"code": "JAI", "name": "Jaipur", "display": "Jaipur"},
    "kochi": {"code": "COK", "name": "Kochi", "display": "Kochi"},
    "cochin": {"code": "COK", "name": "Kochi", "display": "Kochi"},
    "lucknow": {"code": "LKO", "name": "Lucknow", "display": "Lucknow"},
    "patna": {"code": "PAT", "name": "Patna", "display": "Patna"},
    "bhopal": {"code": "BHO", "name": "Bhopal", "display": "Bhopal"},
    "varanasi": {"code": "VNS", "name": "Varanasi", "display": "Varanasi"},
    "indore": {"code": "IDR", "name": "Indore", "display": "Indore"},
    "nagpur": {"code": "NAG", "name": "Nagpur", "display": "Nagpur"},
    "visakhapatnam": {"code": "VTZ", "name": "Visakhapatnam", "display": "Visakhapatnam"},
    "vizag": {"code": "VTZ", "name": "Visakhapatnam", "display": "Visakhapatnam"},
}

DATE_KEYWORDS = {
    "today": 0,
    "tomorrow": 1,
    "day after tomorrow": 2,
    "overmorrow": 2,
}


class PlannerAgent:
    """
    Planner Agent: Converts natural language query to structured flight search plan.
    """
    
    def __init__(self):
        self.logger = AgentLogger("planner")
        # Optional Groq free-tier client (no key = pure regex mode)
        groq_key = os.getenv("GROQ_API_KEY", "")
        self.groq_client = None
        if _GROQ_AVAILABLE and groq_key:
            try:
                self.groq_client = GroqClient(api_key=groq_key)
                self.logger.info("Groq free-tier LLM enabled for query parsing")
            except Exception:
                self.groq_client = None
        if not self.groq_client:
            self.logger.info("Running in pure regex mode (no API key required)")

    def parse_query(self, query: str) -> dict:
        """Parse user query. Uses Groq free-tier LLM if available, else pure regex."""
        self.logger.info(f"Parsing query: '{query}'")

        # Try Groq-enhanced parsing first (free, but optional)
        if self.groq_client:
            try:
                groq_result = self._parse_with_groq(query)
                if groq_result and groq_result.get("valid"):
                    self.logger.info("Query parsed via Groq free-tier LLM")
                    return groq_result
            except Exception as e:
                self.logger.warning(f"Groq parse failed, falling back to regex: {e}")

        # Pure regex fallback — always works, zero cost
        self.logger.info("Parsing query with regex (free, no API key)")
        query_lower = query.lower().strip()

        # Extract cities
        origin, destination = self._extract_cities(query_lower)
        
        # Extract date
        travel_date = self._extract_date(query_lower)
        
        # Extract passenger count
        passengers = self._extract_passengers(query_lower)
        
        # Extract class
        travel_class = self._extract_class(query_lower)
        
        plan = {
            "parsed": {
                "origin": origin,
                "destination": destination,
                "date": travel_date,
                "passengers": passengers,
                "class": travel_class,
                "raw_query": query,
            },
            "steps": self._build_steps(origin, destination, travel_date, passengers, travel_class),
            "valid": bool(origin and destination),
        }
        
        if not plan["valid"]:
            plan["error"] = self._build_error(origin, destination)
        
        self.logger.info(f"Parsed: {origin} → {destination} on {travel_date}")
        return plan

    def _parse_with_groq(self, query: str) -> dict:
        """Use Groq free-tier LLM to parse the query (llama3-8b, 14,400 req/day free)."""
        import json

        system_prompt = """You are a flight search parser. Extract flight details from the user query.
Return ONLY valid JSON, no explanation. Format:
{
  "origin_city": "city name exactly as spelled in India",
  "destination_city": "city name exactly as spelled in India",
  "date_offset_days": 0,
  "date_explicit": "DD/MM/YYYY or null",
  "passengers": 1,
  "class": "Economy"
}
date_offset_days: 0=today, 1=tomorrow, 2=day after. Use date_explicit for specific dates."""

        response = self.groq_client.chat.completions.create(
            model="llama3-8b-8192",   # Free on Groq
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": query},
            ],
            temperature=0,
            max_tokens=200,
        )
        raw = response.choices[0].message.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1].lstrip("json").strip()

        parsed_llm = json.loads(raw)

        # Map LLM output to our CITIES dict
        origin_str = parsed_llm.get("origin_city", "").lower()
        dest_str = parsed_llm.get("destination_city", "").lower()
        origin = CITIES.get(origin_str)
        destination = CITIES.get(dest_str)

        # fuzzy match if exact key missing
        if not origin:
            for k, v in CITIES.items():
                if origin_str in k or k in origin_str:
                    origin = v; break
        if not destination:
            for k, v in CITIES.items():
                if dest_str in k or k in dest_str:
                    destination = v; break

        # Resolve date
        from datetime import datetime, timedelta
        if parsed_llm.get("date_explicit"):
            travel_date = parsed_llm["date_explicit"]
        else:
            offset = int(parsed_llm.get("date_offset_days", 1))
            travel_date = (datetime.now() + timedelta(days=offset)).strftime("%d/%m/%Y")

        passengers = int(parsed_llm.get("passengers", 1))
        travel_class = parsed_llm.get("class", "Economy")

        plan = {
            "parsed": {
                "origin": origin,
                "destination": destination,
                "date": travel_date,
                "passengers": passengers,
                "class": travel_class,
                "raw_query": query,
            },
            "steps": self._build_steps(origin, destination, travel_date, passengers, travel_class),
            "valid": bool(origin and destination),
        }
        if not plan["valid"]:
            plan["error"] = self._build_error(origin, destination)
        return plan

    def _extract_cities(self, query: str) -> tuple[Optional[dict], Optional[dict]]:
        """Extract origin and destination cities from query"""
        
        # Pattern: "X to Y", "from X to Y", "X → Y"
        to_patterns = [
            r"(?:from\s+)?(\w+(?:\s+\w+)?)\s+to\s+(\w+(?:\s+\w+)?)",
            r"(\w+(?:\s+\w+)?)\s*[→\-]\s*(\w+(?:\s+\w+)?)",
        ]
        
        for pattern in to_patterns:
            match = re.search(pattern, query)
            if match:
                origin_str = match.group(1).strip().lower()
                dest_str = match.group(2).strip().lower()
                
                # Remove date keywords from city names
                for keyword in ["tomorrow", "today", "tonight", "morning", "evening"]:
                    origin_str = origin_str.replace(keyword, "").strip()
                    dest_str = dest_str.replace(keyword, "").strip()
                
                origin = CITIES.get(origin_str)
                dest = CITIES.get(dest_str)
                
                if origin and dest:
                    return origin, dest
        
        # Fallback: find any two city mentions in order
        found = []
        # Sort by position of first occurrence
        for city_name, city_data in CITIES.items():
            pos = query.find(city_name)
            if pos >= 0:
                found.append((pos, city_data))
        
        found.sort(key=lambda x: x[0])
        unique = []
        seen_codes = set()
        for _, city in found:
            if city["code"] not in seen_codes:
                unique.append(city)
                seen_codes.add(city["code"])
        
        if len(unique) >= 2:
            return unique[0], unique[1]
        
        return None, None

    def _extract_date(self, query: str) -> str:
        """Extract travel date from query"""
        today = datetime.now()
        
        # Check relative keywords
        for keyword, offset in DATE_KEYWORDS.items():
            if keyword in query:
                target = today + timedelta(days=offset)
                return target.strftime("%d/%m/%Y")
        
        # Check "next Monday", "this Friday", etc.
        weekdays = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(weekdays):
            if day in query:
                days_ahead = (i - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7  # Next week
                target = today + timedelta(days=days_ahead)
                return target.strftime("%d/%m/%Y")
        
        # Check explicit dates: "12 jan", "12/01", "12-01-2025"
        date_patterns = [
            r"(\d{1,2})[\/\-](\d{1,2})[\/\-](\d{4})",
            r"(\d{1,2})[\/\-](\d{1,2})",
            r"(\d{1,2})\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\w*",
        ]
        
        months = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
            "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
        }
        
        for pattern in date_patterns:
            match = re.search(pattern, query)
            if match:
                groups = match.groups()
                if len(groups) == 3 and groups[2].isdigit():
                    return f"{groups[0].zfill(2)}/{groups[1].zfill(2)}/{groups[2]}"
                elif len(groups) == 2 and groups[1].isdigit():
                    year = today.year
                    return f"{groups[0].zfill(2)}/{groups[1].zfill(2)}/{year}"
                elif len(groups) == 2:
                    month = months.get(groups[1][:3], today.month)
                    year = today.year
                    return f"{groups[0].zfill(2)}/{str(month).zfill(2)}/{year}"
        
        # Default: tomorrow
        tomorrow = today + timedelta(days=1)
        return tomorrow.strftime("%d/%m/%Y")

    def _extract_passengers(self, query: str) -> int:
        """Extract number of passengers"""
        match = re.search(r"(\d+)\s*(?:passenger|person|people|adult|pax)", query)
        if match:
            return min(int(match.group(1)), 9)
        return 1

    def _extract_class(self, query: str) -> str:
        """Extract travel class"""
        if any(w in query for w in ["business", "biz", "business class"]):
            return "Business"
        if any(w in query for w in ["first class", "first"]):
            return "First"
        if any(w in query for w in ["premium economy", "premium"]):
            return "Premium Economy"
        return "Economy"

    def _build_steps(self, origin, destination, date, passengers, travel_class) -> list:
        """Build execution steps for the workflow"""
        steps = [
            {
                "id": 1,
                "name": "open_website",
                "description": "Open MakeMyTrip website",
                "agent": "browser",
                "action": "navigate",
                "url": "https://www.makemytrip.com/",
            },
            {
                "id": 2,
                "name": "handle_popups",
                "description": "Close any login popups or banners",
                "agent": "browser",
                "action": "close_popups",
            },
            {
                "id": 3,
                "name": "select_one_way",
                "description": "Select one-way trip option",
                "agent": "browser",
                "action": "click_one_way",
            },
            {
                "id": 4,
                "name": "enter_origin",
                "description": f"Enter origin city: {origin['display'] if origin else 'N/A'}",
                "agent": "browser",
                "action": "fill_origin",
                "value": origin["display"] if origin else "",
            },
            {
                "id": 5,
                "name": "enter_destination",
                "description": f"Enter destination: {destination['display'] if destination else 'N/A'}",
                "agent": "browser",
                "action": "fill_destination",
                "value": destination["display"] if destination else "",
            },
            {
                "id": 6,
                "name": "select_date",
                "description": f"Select travel date: {date}",
                "agent": "browser",
                "action": "fill_date",
                "value": date,
            },
            {
                "id": 7,
                "name": "search_flights",
                "description": "Click Search Flights button",
                "agent": "browser",
                "action": "click_search",
            },
            {
                "id": 8,
                "name": "wait_for_results",
                "description": "Wait for flight results to load",
                "agent": "browser",
                "action": "wait_results",
            },
            {
                "id": 9,
                "name": "extract_flights",
                "description": "Extract all flight data from results page",
                "agent": "extraction",
                "action": "extract_flights",
            },
            {
                "id": 10,
                "name": "present_results",
                "description": "Display extracted flights to user",
                "agent": "orchestrator",
                "action": "present_flights",
            },
            {
                "id": 11,
                "name": "select_flight",
                "description": "User selects a flight",
                "agent": "orchestrator",
                "action": "await_selection",
            },
            {
                "id": 12,
                "name": "fill_passenger",
                "description": "Fill in passenger details",
                "agent": "form_filling",
                "action": "fill_passenger_form",
            },
            {
                "id": 13,
                "name": "stop_before_payment",
                "description": "Halt workflow before payment page",
                "agent": "orchestrator",
                "action": "stop_before_payment",
            },
        ]
        return steps

    def _build_error(self, origin, destination) -> str:
        if not origin and not destination:
            return "Could not identify origin or destination cities. Please specify e.g. 'Hyderabad to Delhi tomorrow'"
        if not origin:
            return "Could not identify the origin city. Please specify e.g. 'from Hyderabad'"
        if not destination:
            return "Could not identify the destination city. Please specify e.g. 'to Delhi'"
        return "Invalid query"
