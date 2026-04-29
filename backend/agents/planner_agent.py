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

        # Extract round trip info (basic regex fallback)
        is_round_trip = False
        return_date = None
        if any(w in query_lower for w in ["return", "round trip", "roundtrip", "come back"]):
            is_round_trip = True
            # very naive fallback for return date
            return_date = self._extract_date(query_lower.split("return")[-1] if "return" in query_lower else query_lower)

        # Determine if user explicitly mentioned a date (vs. us defaulting "tomorrow")
        has_explicit_date = self._has_explicit_date_hint(query_lower)

        plan = {
            "parsed": {
                "origin": origin,
                "destination": destination,
                "date": travel_date,
                "is_round_trip": is_round_trip,
                "return_date": return_date,
                "passengers": passengers,
                "class": travel_class,
                "raw_query": query,
            },
            "steps": self._build_steps(origin, destination, travel_date, passengers, travel_class, is_round_trip, return_date),
            # "valid" = we can technically run the workflow (cities known)
            "valid": bool(origin and destination),
            # "complete" = we have all key user preferences, including an explicitly stated date
            "complete": bool(origin and destination and has_explicit_date),
        }

        # Build clarification questions whenever the request is incomplete
        if not plan["complete"]:
            plan["clarification_questions"] = self._generate_clarification_questions(
                origin,
                destination,
                travel_date,
                query_lower,
                has_explicit_date=has_explicit_date,
            )

        if not plan["valid"]:
            plan["error"] = self._build_error(origin, destination)

        self.logger.info(f"Parsed: {origin} → {destination} on {travel_date}")
        return plan

    def _parse_with_groq(self, query: str) -> dict:
        """Use Groq free-tier LLM to parse the query."""
        try:
            system_prompt = """You are a flight search parser. Extract flight details from the user query.
Return ONLY valid JSON. Format:
{
  "origin_city": "city name or null",
  "origin_code": "IATA code or null",
  "destination_city": "city name or null",
  "destination_code": "IATA code or null",
  "date_explicit": "DD/MM/YYYY or null",
  "date_offset_days": 0,
  "is_round_trip": false,
  "return_date_explicit": "DD/MM/YYYY or null",
  "passengers": 1,
  "class": "Economy"
}"""
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": query},
                ],
                temperature=0,
                max_tokens=300,
            )
            raw = response.choices[0].message.content.strip()
            if "```" in raw:
                raw = raw.split("```")[1].replace("json", "").strip()
            
            parsed_llm = json.loads(raw)
            self.logger.info(f"Groq LLM raw output: {raw}")

            # Extract fields with safe defaults
            o_city = parsed_llm.get("origin_city")
            d_city = parsed_llm.get("destination_city")
            o_code = parsed_llm.get("origin_code")
            d_code = parsed_llm.get("destination_code")

            origin = None
            if o_city:
                # Try lookup in our CITIES
                origin = CITIES.get(o_city.lower())
            if not origin and o_code:
                origin = {"code": o_code.upper(), "name": o_city or "Unknown", "display": o_city or "Unknown"}
            
            destination = None
            if d_city:
                destination = CITIES.get(d_city.lower())
            if not destination and d_code:
                destination = {"code": d_code.upper(), "name": d_city or "Unknown", "display": d_city or "Unknown"}

            # Resolve date
            date_explicit = parsed_llm.get("date_explicit")
            date_offset_days = parsed_llm.get("date_offset_days", 1)
            if date_explicit:
                travel_date = date_explicit
            else:
                offset = int(date_offset_days or 1)
                travel_date = (datetime.now() + timedelta(days=offset)).strftime("%d/%m/%Y")

            passengers = int(parsed_llm.get("passengers", 1))
            travel_class = parsed_llm.get("class", "Economy")
            is_round_trip = bool(parsed_llm.get("is_round_trip", False))
            return_date = parsed_llm.get("return_date_explicit") if is_round_trip else None

            has_explicit_date = bool(date_explicit or date_offset_days not in (None, "", 0))

            plan = {
                "parsed": {
                    "origin": origin,
                    "destination": destination,
                    "date": travel_date,
                    "is_round_trip": is_round_trip,
                    "return_date": return_date,
                    "passengers": passengers,
                    "class": travel_class,
                    "raw_query": query,
                },
                "steps": self._build_steps(origin, destination, travel_date, passengers, travel_class, is_round_trip, return_date),
                "valid": bool(origin and destination),
                "complete": bool(origin and destination and has_explicit_date),
            }
            if not plan["complete"]:
                plan["clarification_questions"] = self._generate_clarification_questions(
                    origin,
                    destination,
                    travel_date,
                    query.lower(),
                    has_explicit_date=has_explicit_date,
                )
            if not plan["valid"]:
                plan["error"] = self._build_error(origin, destination)
            return plan
        except Exception as e:
            self.logger.error(f"Error in _parse_with_groq: {e}")
            raise e

    def _extract_cities(self, query: str) -> tuple[Optional[dict], Optional[dict]]:
        """Extract origin and destination cities from query"""

        from_match = self._match_city_after_keyword(query, "from")
        to_match = self._match_city_after_keyword(query, "to")

        # Prefer explicit "from X" / "to Y" extraction because clarification
        # replies can arrive in either order: "from Hyderabad to Delhi" or
        # "to Delhi from Hyderabad".
        if from_match and to_match:
            origin = CITIES.get(from_match)
            destination = CITIES.get(to_match)
            if origin and destination:
                return origin, destination

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

        # Handle incomplete phrases explicitly so we ask for the right thing:
        # "from Hyderabad" => origin known, destination missing
        from_only_match = from_match
        if from_only_match:
            origin = CITIES.get(from_only_match)
            if origin:
                return origin, None

        # "to Delhi" => destination known, origin missing
        to_only_match = to_match
        if to_only_match:
            destination = CITIES.get(to_only_match)
            if destination:
                return None, destination

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
        elif len(unique) == 1:
            if "from" in query:
                return unique[0], None
            if "to" in query or "→" in query or "-" in query:
                return None, unique[0]
            return unique[0], None

        return None, None

    def _match_city_after_keyword(
        self,
        query: str,
        keyword: str,
    ) -> Optional[str]:
        """Return the known city name that appears immediately after a keyword."""
        marker = f"{keyword} "
        start = query.find(marker)
        if start < 0:
            return None

        remainder = query[start + len(marker):].strip()
        for city_name in sorted(CITIES.keys(), key=len, reverse=True):
            if remainder == city_name or remainder.startswith(f"{city_name} "):
                return city_name

        return None

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

    def _build_steps(self, origin, destination, date, passengers, travel_class, is_round_trip=False, return_date=None) -> list:
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
                "name": "select_trip_type",
                "description": "Select round-trip option" if is_round_trip else "Select one-way trip option",
                "agent": "browser",
                "action": "click_round_trip" if is_round_trip else "click_one_way",
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
            }
        ]
        
        if is_round_trip and return_date:
            steps.append({
                "id": 6.5,
                "name": "select_return_date",
                "description": f"Select return date: {return_date}",
                "agent": "browser",
                "action": "fill_return_date",
                "value": return_date,
            })
            
        steps.extend([
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
        ])
        return steps

    def _has_explicit_date_hint(self, query_lower: str) -> bool:
        """
        Heuristic: did the user explicitly mention *when* they want to travel?
        We check for relative/weekday/month/date patterns in the raw text.
        """
        if any(k in query_lower for k in DATE_KEYWORDS.keys()):
            return True

        if any(d in query_lower for d in [
            "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"
        ]):
            return True

        if any(m in query_lower for m in [
            "jan", "feb", "mar", "apr", "may", "jun",
            "jul", "aug", "sep", "oct", "nov", "dec"
        ]):
            return True

        # Simple numeric date patterns like 12/01 or 12-01-2026
        if re.search(r"\d{1,2}[\/\-]\d{1,2}(?:[\/\-]\d{2,4})?", query_lower):
            return True

        return False

    def _generate_clarification_questions(
        self,
        origin,
        destination,
        travel_date,
        query_lower: str,
        has_explicit_date: bool,
    ) -> list:
        """Generate clarification questions for missing or implicit information."""
        questions = []

        if not origin:
            questions.append({
                "type": "origin",
                "question": "Which city are you flying from? (e.g., Hyderabad, Delhi, Mumbai, Bangalore, etc.)",
                "examples": list(set([city.replace("_", " ") for city in CITIES.keys()]))[:10]
            })

        if not destination:
            questions.append({
                "type": "destination",
                "question": "Which city would you like to travel to? (e.g., Delhi, Mumbai, Bangalore, Goa, etc.)",
                "examples": list(set([city.replace("_", " ") for city in CITIES.keys()]))[:10]
            })

        # Ask for date only if user didn't clearly specify it
        if not has_explicit_date:
            questions.append({
                "type": "date",
                "question": "When do you want to travel? (e.g., tomorrow, 15 May, next Monday, etc.)",
                "examples": ["tomorrow", "day after tomorrow", "15 May", "next Monday", "25/05/2025"]
            })

        return questions

    def _build_error(self, origin, destination) -> str:
        if not origin and not destination:
            return "Could not identify origin or destination cities. Please specify e.g. 'Hyderabad to Delhi tomorrow'"
        if not origin:
            return "Could not identify the origin city. Please specify e.g. 'from Hyderabad'"
        if not destination:
            return "Could not identify the destination city. Please specify e.g. 'to Delhi'"
        return "Invalid query"
