"""
Extraction Agent
Parses flight results page HTML to extract structured flight data.
Implements multiple parsing strategies with fallback to vision.
"""

import re
import json
import os
import httpx
from typing import List, Optional
from bs4 import BeautifulSoup

from utils.logger import AgentLogger


class ExtractionAgent:
    """
    Extraction Agent: Parses MakeMyTrip flight results into structured JSON.
    Tries multiple CSS patterns and falls back to heuristic text parsing.
    """

    # Various selectors MakeMyTrip has used over time
    FLIGHT_CARD_SELECTORS = [
        ".listingCard",
        ".flt-info",
        ".fliCard",
        ".air-itinerary",
        "[data-cy='flightCard']",
        ".flight-card",
        ".result-item",
        ".resultsUi .flt-booking-wrapper",
        ".flightItinerary",
        ".airlineDetails",
    ]

    def __init__(self):
        self.logger = AgentLogger("extraction")

    async def fetch_flights_from_apis(self, origin: str, destination: str, date: str, return_date: str = None) -> List[dict]:
        """Try fetching flights from configured APIs sequentially."""
        self.logger.info("Checking configured APIs for flight data...")
        
        # 1. Try SerpApi
        flights = await self._fetch_serpapi(origin, destination, date, return_date)
        if flights: return flights
        
        # 2. Try Amadeus
        flights = await self._fetch_amadeus(origin, destination, date, return_date)
        if flights: return flights
        
        # 3. Try RapidAPI
        flights = await self._fetch_rapidapi(origin, destination, date, return_date)
        if flights: return flights
        
        self.logger.warning("All APIs failed or no API keys configured.")
        return []

    async def _fetch_serpapi(self, origin: str, destination: str, date: str, return_date: str = None) -> List[dict]:
        api_key = os.getenv("SERPAPI_API_KEY")
        if not api_key: return []
        self.logger.info("Attempting SerpApi Google Flights extraction...")
        
        try:
            d, m, y = date.split("/")
            formatted_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            
            url = "https://serpapi.com/search"
            params = {
                "engine": "google_flights",
                "departure_id": origin,
                "arrival_id": destination,
                "outbound_date": formatted_date,
                "currency": "INR",
                "hl": "en",
                "api_key": api_key,
                "type": "1" if return_date else "2"
            }
            
            if return_date:
                rd, rm, ry = return_date.split("/")
                params["return_date"] = f"{ry}-{rm.zfill(2)}-{rd.zfill(2)}"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=15.0)
                if response.status_code != 200:
                    self.logger.warning(f"SerpApi error: {response.status_code}")
                    return []
                
                data = response.json()
                flights = []
                best_flights = data.get("best_flights", [])
                other_flights = data.get("other_flights", [])
                all_flights = best_flights + other_flights
                
                for i, f in enumerate(all_flights[:20]):
                    fl = f.get("flights", [{}])[0]
                    price = f.get("price", 0)
                    
                    departure_time = fl.get("departure_airport", {}).get("time", "")
                    if departure_time and len(departure_time) >= 5: departure_time = departure_time[-5:]
                    
                    arrival_time = fl.get("arrival_airport", {}).get("time", "")
                    if arrival_time and len(arrival_time) >= 5: arrival_time = arrival_time[-5:]
                    
                    flights.append({
                        "index": i,
                        "airline": fl.get("airline", "Unknown"),
                        "flight_number": fl.get("flight_number", ""),
                        "departure_time": departure_time,
                        "arrival_time": arrival_time,
                        "duration": f"{f.get('total_duration', 0)//60}h {f.get('total_duration', 0)%60}m",
                        "price": f"₹{price:,}",
                        "stops": "Non-stop" if len(f.get("flights", [])) <= 1 else f"{len(f.get('flights'))-1} Stop"
                    })
                
                if flights:
                    self.logger.success(f"SerpApi retrieved {len(flights)} flights")
                    return flights
        except Exception as e:
            self.logger.warning(f"SerpApi extraction failed: {e}")
        return []

    async def _fetch_amadeus(self, origin: str, destination: str, date: str, return_date: str = None) -> List[dict]:
        client_id = os.getenv("AMADEUS_CLIENT_ID")
        client_secret = os.getenv("AMADEUS_CLIENT_SECRET")
        if not client_id or not client_secret: return []
        
        self.logger.info("Attempting Amadeus API extraction...")
        try:
            d, m, y = date.split("/")
            formatted_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            
            async with httpx.AsyncClient() as client:
                token_url = "https://test.api.amadeus.com/v1/security/oauth2/token"
                token_data = {
                    "grant_type": "client_credentials",
                    "client_id": client_id,
                    "client_secret": client_secret
                }
                token_res = await client.post(token_url, data=token_data, timeout=10.0)
                if token_res.status_code != 200:
                    self.logger.warning("Amadeus authentication failed")
                    return []
                
                access_token = token_res.json().get("access_token")
                
                search_url = "https://test.api.amadeus.com/v2/shopping/flight-offers"
                headers = {"Authorization": f"Bearer {access_token}"}
                params = {
                    "originLocationCode": origin,
                    "destinationLocationCode": destination,
                    "departureDate": formatted_date,
                    "adults": 1,
                    "currencyCode": "INR",
                    "max": 20
                }
                
                search_res = await client.get(search_url, headers=headers, params=params, timeout=15.0)
                if search_res.status_code != 200:
                    self.logger.warning("Amadeus search failed")
                    return []
                
                data = search_res.json()
                dictionaries = data.get("dictionaries", {})
                carriers = dictionaries.get("carriers", {})
                
                flights = []
                for i, offer in enumerate(data.get("data", [])):
                    price = int(float(offer.get("price", {}).get("total", 0)))
                    itinerary = offer.get("itineraries", [{}])[0]
                    segments = itinerary.get("segments", [])
                    if not segments: continue
                    
                    first_seg = segments[0]
                    last_seg = segments[-1]
                    
                    carrier_code = first_seg.get("carrierCode")
                    airline = carriers.get(carrier_code, carrier_code)
                    
                    dep_time = first_seg.get("departure", {}).get("at", "")[11:16]
                    arr_time = last_seg.get("arrival", {}).get("at", "")[11:16]
                    
                    dur_pt = itinerary.get("duration", "PT0H0M")
                    dur_match = re.search(r'PT(?:(\d+)H)?(?:(\d+)M)?', dur_pt)
                    dur_h = dur_match.group(1) or "0" if dur_match else "0"
                    dur_m = dur_match.group(2) or "0" if dur_match else "0"
                    
                    stops = len(segments) - 1
                    
                    flights.append({
                        "index": i,
                        "airline": airline,
                        "flight_number": f"{carrier_code}{first_seg.get('number', '')}",
                        "departure_time": dep_time,
                        "arrival_time": arr_time,
                        "duration": f"{dur_h}h {dur_m}m",
                        "price": f"₹{price:,}",
                        "stops": "Non-stop" if stops == 0 else f"{stops} Stop(s)"
                    })
                    
                if flights:
                    self.logger.success(f"Amadeus retrieved {len(flights)} flights")
                    return flights
        except Exception as e:
            self.logger.warning(f"Amadeus extraction failed: {e}")
        return []

    async def _fetch_rapidapi(self, origin: str, destination: str, date: str, return_date: str = None) -> List[dict]:
        api_key = os.getenv("RAPIDAPI_KEY")
        api_host = os.getenv("RAPIDAPI_HOST", "booking-com15.p.rapidapi.com")
        if not api_key: return []
        
        self.logger.info(f"Attempting RapidAPI ({api_host}) extraction...")
        try:
            d, m, y = date.split("/")
            formatted_date = f"{y}-{m.zfill(2)}-{d.zfill(2)}"
            
            url = f"https://{api_host}/api/v1/flights/searchFlights"
            
            params = {
                "fromId": f"{origin}.AIRPORT",
                "toId": f"{destination}.AIRPORT",
                "pageNo": 1,
                "adults": 1,
                "sort": "BEST",
                "cabinClass": "ECONOMY",
                "currency_code": "INR",
                "departDate": formatted_date
            }
            
            headers = {
                "x-rapidapi-key": api_key,
                "x-rapidapi-host": api_host
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, headers=headers, params=params, timeout=15.0)
                if response.status_code != 200:
                    self.logger.warning(f"RapidAPI error: {response.status_code}")
                    return []
                
                data = response.json()
                flight_offers = data.get("data", {}).get("flightOffers", [])
                
                flights = []
                for i, offer in enumerate(flight_offers[:20]):
                    price = int(offer.get("priceBreakdown", {}).get("total", {}).get("units", 0))
                    
                    segments = offer.get("segments", [])
                    if not segments: continue
                    segment = segments[0]
                    legs = segment.get("legs", [])
                    if not legs: continue
                    
                    first_leg = legs[0]
                    last_leg = legs[-1]
                    
                    carriers_data = first_leg.get("carriersData", [{}])
                    carrier_name = carriers_data[0].get("name", "Unknown") if carriers_data else "Unknown"
                    carrier_code = first_leg.get("flightInfo", {}).get("carrierInfo", {}).get("operatingCarrier", "")
                    flight_num = first_leg.get("flightInfo", {}).get("flightNumber", "")
                    
                    dep_time = first_leg.get("departureTime", "")[11:16]
                    arr_time = last_leg.get("arrivalTime", "")[11:16]
                    
                    dur_sec = segment.get("totalTime", 0)
                    dur_min = dur_sec // 60
                    
                    stops = len(legs) - 1
                    
                    flights.append({
                        "index": i,
                        "airline": carrier_name,
                        "flight_number": f"{carrier_code}{flight_num}",
                        "departure_time": dep_time,
                        "arrival_time": arr_time,
                        "duration": f"{dur_min//60}h {dur_min%60}m",
                        "price": f"₹{price:,}",
                        "stops": "Non-stop" if stops == 0 else f"{stops} Stop(s)"
                    })
                    
                if flights:
                    self.logger.success(f"RapidAPI retrieved {len(flights)} flights")
                    return flights
        except Exception as e:
            self.logger.warning(f"RapidAPI extraction failed: {e}")
        return []

    def extract_flights(self, html: str) -> List[dict]:
        """
        Main extraction method. Tries multiple strategies.
        Returns list of flight dicts.
        """
        self.logger.info("Starting flight data extraction...")
        
        soup = BeautifulSoup(html, "html.parser")
        
        # Strategy 1: JSON-LD / embedded data
        flights = self._extract_from_json_ld(soup)
        if flights:
            self.logger.success(f"Extracted {len(flights)} flights via JSON-LD")
            return flights
        
        # Strategy 2: Structured card selectors
        flights = self._extract_from_cards(soup)
        if flights:
            self.logger.success(f"Extracted {len(flights)} flights via card selectors")
            return flights
        
        # Strategy 3: Heuristic text mining
        flights = self._extract_heuristic(soup)
        if flights:
            self.logger.success(f"Extracted {len(flights)} flights via heuristic")
            return flights
        
        self.logger.warning("No flights extracted from HTML")
        return []

    def _extract_from_json_ld(self, soup: BeautifulSoup) -> List[dict]:
        """Try to extract from embedded JSON data"""
        scripts = soup.find_all("script")
        
        for script in scripts:
            text = script.string or ""
            
            # Look for window.__data or similar embedded JSON
            patterns = [
                r"window\.__data\s*=\s*({.+?});",
                r"window\.INITIAL_STATE\s*=\s*({.+?});",
                r'"flights"\s*:\s*(\[.+?\])',
                r'"flightList"\s*:\s*(\[.+?\])',
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, re.DOTALL)
                if match:
                    try:
                        data = json.loads(match.group(1))
                        flights = self._parse_json_flight_data(data)
                        if flights:
                            return flights
                    except (json.JSONDecodeError, Exception):
                        continue
        
        return []

    def _extract_from_cards(self, soup: BeautifulSoup) -> List[dict]:
        """Extract using known card/container selectors"""
        cards = []
        
        for selector in self.FLIGHT_CARD_SELECTORS:
            # Convert CSS selector to BeautifulSoup-compatible
            class_name = selector.lstrip(".")
            if selector.startswith("."):
                found = soup.find_all(class_=re.compile(re.escape(class_name), re.I))
            elif selector.startswith("["):
                # data-cy attribute
                attr_match = re.match(r'\[([^=]+)="([^"]+)"\]', selector)
                if attr_match:
                    found = soup.find_all(attrs={attr_match.group(1): attr_match.group(2)})
                else:
                    continue
            else:
                found = soup.find_all(selector)
            
            if found and len(found) >= 1:
                cards = found
                self.logger.info(f"Found {len(cards)} cards with selector: {selector}")
                break
        
        if not cards:
            return []
        
        flights = []
        for i, card in enumerate(cards[:20]):  # Max 20 flights
            flight = self._parse_card(card, i)
            if flight:
                flights.append(flight)
        
        return flights

    def _parse_card(self, card, index: int) -> Optional[dict]:
        """Parse a single flight card element"""
        text = card.get_text(separator=" ", strip=True)
        
        if len(text) < 20:
            return None
        
        flight = {"index": index}
        
        # Airline name - look for common patterns
        airline = self._extract_airline(card, text)
        flight["airline"] = airline or "Unknown Airline"
        
        # Flight number
        fn_match = re.search(r"\b([A-Z]{2,3}[\s-]?\d{3,4})\b", text)
        flight["flight_number"] = fn_match.group(1) if fn_match else ""
        
        # Times - looking for HH:MM patterns
        times = re.findall(r"\b(\d{1,2}:\d{2}(?:\s*[AP]M)?)\b", text, re.I)
        if len(times) >= 2:
            flight["departure_time"] = times[0]
            flight["arrival_time"] = times[1]
        elif len(times) == 1:
            flight["departure_time"] = times[0]
            flight["arrival_time"] = ""
        else:
            flight["departure_time"] = ""
            flight["arrival_time"] = ""
        
        # Duration
        dur_match = re.search(r"(\d+h\s*\d*m|\d+\s*hrs?\s*\d*\s*mins?)", text, re.I)
        flight["duration"] = dur_match.group(1) if dur_match else ""
        
        # Price - INR amounts
        price_match = re.search(r"[₹Rs\.]*\s*([0-9,]{3,8})", text)
        if price_match:
            price_val = price_match.group(1).replace(",", "")
            flight["price"] = f"₹{int(price_val):,}" if price_val.isdigit() else price_match.group(0)
        else:
            flight["price"] = "Price N/A"
        
        # Stops
        if re.search(r"non.?stop|0 stop|direct", text, re.I):
            flight["stops"] = "Non-stop"
        else:
            stops_match = re.search(r"(\d+)\s*stop", text, re.I)
            flight["stops"] = f"{stops_match.group(1)} Stop(s)" if stops_match else "1 Stop"
        
        return flight

    def _extract_airline(self, card, text: str) -> Optional[str]:
        """Extract airline name from card"""
        known_airlines = [
            "IndiGo", "Air India", "SpiceJet", "Vistara", "GoAir", "Go First",
            "AirAsia", "Blue Dart", "Alliance Air", "Star Air",
            "Akasa Air", "Air India Express", "TruJet",
        ]
        
        for airline in known_airlines:
            if airline.lower() in text.lower():
                return airline
        
        # Look for airline logo alt text
        imgs = card.find_all("img")
        for img in imgs:
            alt = img.get("alt", "")
            if alt and len(alt) > 2 and not any(c.isdigit() for c in alt):
                return alt
        
        # Look for airline-specific classes
        airline_el = card.find(class_=re.compile(r"airline|carrier", re.I))
        if airline_el:
            name = airline_el.get_text(strip=True)
            if name and len(name) > 2:
                return name
        
        return None

    def _extract_heuristic(self, soup: BeautifulSoup) -> List[dict]:
        """Last-resort heuristic extraction from page text"""
        # Find sections with flight-like patterns
        all_text = soup.get_text(separator="\n")
        lines = [l.strip() for l in all_text.split("\n") if l.strip()]
        
        flights = []
        i = 0
        flight_count = 0
        
        while i < len(lines) and flight_count < 15:
            line = lines[i]
            
            # Look for time patterns that indicate a flight row
            if re.search(r"\d{1,2}:\d{2}", line):
                times = re.findall(r"\d{1,2}:\d{2}(?:\s*[AP]M)?", line, re.I)
                if len(times) >= 2:
                    # Look for price in nearby lines
                    context = " ".join(lines[max(0, i-3):min(len(lines), i+4)])
                    price_match = re.search(r"[₹Rs]\s*([0-9,]{3,8})", context)
                    
                    if price_match:
                        price_val = price_match.group(1).replace(",", "")
                        flight = {
                            "index": flight_count,
                            "airline": self._find_airline_near(lines, i),
                            "flight_number": "",
                            "departure_time": times[0],
                            "arrival_time": times[1],
                            "duration": "",
                            "price": f"₹{int(price_val):,}" if price_val.isdigit() else price_match.group(0),
                            "stops": "Non-stop" if re.search(r"non.?stop|direct", context, re.I) else "1 Stop",
                        }
                        flights.append(flight)
                        flight_count += 1
            i += 1
        
        return flights

    def _find_airline_near(self, lines: list, index: int) -> str:
        """Find airline name in lines surrounding a flight row"""
        known_airlines = [
            "IndiGo", "Air India", "SpiceJet", "Vistara", "GoAir",
            "AirAsia", "Akasa", "Go First",
        ]
        
        context_lines = lines[max(0, index-4):index+2]
        for line in context_lines:
            for airline in known_airlines:
                if airline.lower() in line.lower():
                    return airline
        
        return "Unknown Airline"

    def _parse_json_flight_data(self, data: dict) -> List[dict]:
        """Parse embedded JSON data structure (varies by site version)"""
        # Try to navigate common data structures
        if isinstance(data, list):
            return [self._json_to_flight(item, i) for i, item in enumerate(data[:20]) if item]
        
        # Recursive search for flight arrays
        if isinstance(data, dict):
            for key in ["flights", "flightList", "results", "data", "items"]:
                if key in data and isinstance(data[key], list):
                    return [self._json_to_flight(item, i) for i, item in enumerate(data[key][:20])]
        
        return []

    def _json_to_flight(self, item: dict, index: int) -> Optional[dict]:
        """Convert a JSON flight object to our standard format"""
        if not isinstance(item, dict):
            return None
        
        def get_any(d, *keys):
            for k in keys:
                if k in d and d[k]:
                    return str(d[k])
            return ""
        
        return {
            "index": index,
            "airline": get_any(item, "airline", "airlineName", "carrier", "name"),
            "flight_number": get_any(item, "flightNumber", "flight_no", "flightNo"),
            "departure_time": get_any(item, "departureTime", "departure", "deptTime"),
            "arrival_time": get_any(item, "arrivalTime", "arrival", "arrTime"),
            "duration": get_any(item, "duration", "flightDuration"),
            "price": get_any(item, "price", "fare", "totalFare", "amount"),
            "stops": get_any(item, "stops", "noOfStops", "layover"),
        }
