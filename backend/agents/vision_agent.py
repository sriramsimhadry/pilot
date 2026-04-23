"""
Vision Agent — FREE / No-API-Key Version
=========================================
Replaces paid Claude vision with a fully local, zero-cost DOM-analysis approach.

Strategy (all free, no external API):
  1. DOM introspection via Playwright JS evaluation
  2. Accessibility-tree text scanning
  3. Bounding-rect geometry for visible-element detection
  4. OCR-free text pattern matching on page source

The `enabled` flag is always True — no API key required.
"""

import re
import asyncio
from typing import Optional
from utils.logger import AgentLogger


# Known MakeMyTrip popup / overlay patterns
POPUP_PATTERNS = [
    # CSS class fragments
    "modal", "overlay", "popup", "login", "signin", "sheet",
    "ILModal", "hsw-login", "commonModal", "loginModal",
    "cookie", "banner", "notification", "alert-bar",
]

# Payment-page URL and text signals
PAYMENT_SIGNALS_URL = ["payment", "pay", "checkout", "transaction"]
PAYMENT_SIGNALS_TEXT = [
    "card number", "cvv", "expiry", "net banking",
    "upi", "pay now", "secure payment", "debit card",
    "credit card", "wallet", "pay ₹", "complete booking",
]


class VisionAgent:
    """
    FREE Vision Agent — uses DOM introspection instead of any paid API.

    All methods return the same dict schema as the old Claude-vision version
    so the orchestrator needs zero changes.
    """

    def __init__(self):
        self.logger = AgentLogger("vision")
        # Always enabled — no API key needed
        self.enabled = True
        self.logger.info("Vision Agent initialised (free DOM-analysis mode — no API key needed)")

    # ──────────────────────────────────────────────────────────────────────────
    # Public interface (same signatures as the paid version)
    # ──────────────────────────────────────────────────────────────────────────

    async def detect_popup(self, page_or_bytes, page=None) -> dict:
        """
        Detect popups / overlays on the current page using DOM inspection.
        Accepts either a Playwright Page object or raw bytes (bytes are ignored;
        pass `page` kwarg when calling with screenshot bytes for compatibility).
        """
        target_page = page if page is not None else (
            page_or_bytes if not isinstance(page_or_bytes, bytes) else None
        )
        if target_page is None:
            return {"has_popup": False, "popup_type": None,
                    "close_button_coordinates": None, "description": "no page available"}

        try:
            result = await target_page.evaluate("""
                () => {
                    const patterns = """ + str(POPUP_PATTERNS).replace("'", '"') + """;
                    let found = null;
                    let closeCoords = null;

                    // Look for visible overlay/modal elements
                    for (const el of document.querySelectorAll('*')) {
                        const cls = (el.className || '').toString().toLowerCase();
                        const id  = (el.id || '').toLowerCase();
                        const isVisible = el.offsetParent !== null &&
                                          el.offsetWidth > 50 && el.offsetHeight > 50;
                        if (!isVisible) continue;

                        const matched = patterns.some(p => cls.includes(p) || id.includes(p));
                        if (matched) {
                            found = cls || id;
                            // Try to find a close button inside
                            const closeBtn = el.querySelector(
                                '[class*="close"], [class*="cancel"], [aria-label="Close"], button[class*="btn"]'
                            );
                            if (closeBtn) {
                                const r = closeBtn.getBoundingClientRect();
                                closeCoords = { x: Math.round(r.left + r.width/2),
                                                y: Math.round(r.top  + r.height/2) };
                            }
                            break;
                        }
                    }
                    return { found, closeCoords };
                }
            """)

            has_popup = bool(result and result.get("found"))
            coords = result.get("closeCoords") if result else None
            self.logger.info(f"Popup scan: {'found' if has_popup else 'none'} — {(result or {}).get('found', '')[:60]}")
            return {
                "has_popup": has_popup,
                "popup_type": "modal" if has_popup else None,
                "close_button_coordinates": coords,
                "description": result.get("found", ""),
            }
        except Exception as e:
            self.logger.warning(f"Popup detection error: {e}")
            return {"has_popup": False, "popup_type": None,
                    "close_button_coordinates": None, "description": str(e)}

    async def find_button(self, page_or_bytes, button_text: str, page=None) -> dict:
        """Find a button by its visible text label using DOM bounding rects."""
        target_page = page if page is not None else (
            page_or_bytes if not isinstance(page_or_bytes, bytes) else None
        )
        if target_page is None:
            return {"found": False, "coordinates": None, "confidence": 0.0}

        try:
            coords = await target_page.evaluate(f"""
                () => {{
                    const text = {repr(button_text.lower())};
                    const candidates = [
                        ...document.querySelectorAll('button, a, [role="button"], input[type="submit"]')
                    ];
                    for (const el of candidates) {{
                        const t = (el.textContent || el.value || el.innerText || '').toLowerCase().trim();
                        if (t.includes(text) && el.offsetParent !== null) {{
                            const r = el.getBoundingClientRect();
                            if (r.width > 0 && r.height > 0) {{
                                return {{ x: Math.round(r.left + r.width/2),
                                          y: Math.round(r.top  + r.height/2) }};
                            }}
                        }}
                    }}
                    return null;
                }}
            """)
            found = coords is not None
            self.logger.info(f"Button '{button_text}': {'found' if found else 'not found'} at {coords}")
            return {"found": found, "coordinates": coords, "confidence": 0.9 if found else 0.0}
        except Exception as e:
            self.logger.warning(f"find_button error: {e}")
            return {"found": False, "coordinates": None, "confidence": 0.0}

    async def find_input(self, page_or_bytes, input_label: str, page=None) -> dict:
        """Find an input field by placeholder text, label, or aria-label."""
        target_page = page if page is not None else (
            page_or_bytes if not isinstance(page_or_bytes, bytes) else None
        )
        if target_page is None:
            return {"found": False, "coordinates": None, "description": ""}

        try:
            coords = await target_page.evaluate(f"""
                () => {{
                    const label = {repr(input_label.lower())};
                    const inputs = [...document.querySelectorAll('input, textarea, select')];
                    for (const el of inputs) {{
                        const ph    = (el.placeholder || '').toLowerCase();
                        const aria  = (el.getAttribute('aria-label') || '').toLowerCase();
                        const name  = (el.name || '').toLowerCase();
                        const id    = (el.id || '').toLowerCase();
                        if ([ph, aria, name, id].some(v => v.includes(label))
                                && el.offsetParent !== null) {{
                            const r = el.getBoundingClientRect();
                            if (r.width > 0) {{
                                return {{ x: Math.round(r.left + r.width/2),
                                          y: Math.round(r.top  + r.height/2) }};
                            }}
                        }}
                    }}
                    return null;
                }}
            """)
            found = coords is not None
            return {"found": found, "coordinates": coords,
                    "description": f"Input '{input_label}' {'located' if found else 'not found'}"}
        except Exception as e:
            return {"found": False, "coordinates": None, "description": str(e)}

    async def analyze_page_state(self, page_or_bytes, page=None) -> dict:
        """
        Determine the current page type (homepage / search / results / booking / payment)
        by inspecting URL, title, and key DOM text — no screenshot needed.
        """
        target_page = page if page is not None else (
            page_or_bytes if not isinstance(page_or_bytes, bytes) else None
        )
        if target_page is None:
            return {"page_type": "unknown", "key_elements": [],
                    "suggested_action": "provide page", "error_detected": False, "error_message": ""}

        try:
            info = await target_page.evaluate("""
                () => ({
                    url:   window.location.href.toLowerCase(),
                    title: document.title.toLowerCase(),
                    body:  document.body ? document.body.innerText.toLowerCase().slice(0, 3000) : '',
                    inputs: [...document.querySelectorAll('input:not([type=hidden])')].length,
                    buttons: [...document.querySelectorAll('button, [role="button"]')]
                                .map(b => b.textContent.trim().slice(0, 40))
                                .filter(Boolean).slice(0, 10),
                })
            """)

            url   = info.get("url", "")
            body  = info.get("body", "")
            btns  = info.get("buttons", [])

            # Classify page
            if any(s in url for s in PAYMENT_SIGNALS_URL):
                page_type = "payment"
            elif any(s in body for s in ["card number", "cvv", "pay now", "net banking"]):
                page_type = "payment"
            elif "flight" in url and ("result" in url or "listing" in url or "search" in url):
                page_type = "results"
            elif "book" in url or "passenger" in url or "traveller" in url:
                page_type = "booking"
            elif info.get("inputs", 0) >= 3 and any(k in body for k in ["from", "to", "departure"]):
                page_type = "search_form"
            elif "makemytrip" in url and info.get("inputs", 0) < 3:
                page_type = "homepage"
            else:
                page_type = "other"

            error_text = ""
            error_detected = any(w in body for w in ["error", "something went wrong", "try again", "oops"])
            if error_detected:
                for line in body.split("\n"):
                    if any(w in line for w in ["error", "wrong", "oops"]):
                        error_text = line.strip()[:120]
                        break

            self.logger.info(f"Page state: {page_type} | URL: {url[:60]}")
            return {
                "page_type": page_type,
                "key_elements": btns,
                "suggested_action": _suggest_action(page_type),
                "error_detected": error_detected,
                "error_message": error_text,
            }
        except Exception as e:
            self.logger.warning(f"analyze_page_state error: {e}")
            return {"page_type": "unknown", "key_elements": [],
                    "suggested_action": "retry", "error_detected": True, "error_message": str(e)}

    async def extract_flight_data_from_screenshot(self, page_or_bytes, page=None) -> dict:
        """
        Extract flight data from the results page via DOM text parsing.
        Falls back gracefully — the orchestrator already has demo-data fallback.
        """
        target_page = page if page is not None else (
            page_or_bytes if not isinstance(page_or_bytes, bytes) else None
        )
        if target_page is None:
            return {"flights": []}

        try:
            # Get visible text from result cards
            raw_text = await target_page.evaluate("""
                () => {
                    const selectors = [
                        '.listingCard', '.fliCard', '.air-itinerary',
                        '.flight-card', '.result-item', '.flt-info'
                    ];
                    let cards = [];
                    for (const sel of selectors) {
                        const found = [...document.querySelectorAll(sel)];
                        if (found.length > 0) {
                            cards = found.map(c => c.innerText);
                            break;
                        }
                    }
                    return cards.slice(0, 15);
                }
            """)

            flights = []
            for i, card_text in enumerate(raw_text or []):
                flight = _parse_card_text(card_text, i)
                if flight:
                    flights.append(flight)

            # If card containers aren't discoverable, parse the visible page text.
            if not flights:
                body_text = await target_page.evaluate(
                    "() => (document.body?.innerText || '').replace(/\\s+/g, ' ').trim()"
                )
                flights = _parse_flights_from_body_text(body_text)

            self.logger.info(f"DOM extraction yielded {len(flights)} flights")
            return {"flights": flights}
        except Exception as e:
            self.logger.warning(f"extract_flight_data error: {e}")
            return {"flights": []}

    def parse_card_texts(self, card_texts: list[str]) -> list[dict]:
        """Parse a list of raw flight-card text blocks into structured flights."""
        flights = []
        for i, text in enumerate(card_texts or []):
            flight = _parse_card_text(text, i)
            if flight:
                flights.append(flight)
        return flights

    # ── Compatibility shim: old code passes screenshot bytes; new code passes page ──
    async def analyze_screenshot(self, screenshot_bytes: bytes, task: str) -> dict:
        """Legacy compatibility method — returns a generic stub (no API needed)."""
        return {"found": False, "error": "screenshot-mode not used in free version"}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _suggest_action(page_type: str) -> str:
    return {
        "homepage": "fill_search_form",
        "search_form": "enter_cities_and_date",
        "results": "extract_flights",
        "booking": "fill_passenger_details",
        "payment": "stop_workflow",
        "other": "wait_and_retry",
    }.get(page_type, "wait_and_retry")


def _parse_card_text(text: str, index: int) -> Optional[dict]:
    """Parse raw card text into a flight dict using regex."""
    if not text or len(text) < 15:
        return None

    times = re.findall(r"\b(\d{1,2}:\d{2}(?:\s*[AP]M)?)\b", text, re.I)
    price = re.search(r"[₹Rs\.]*\s*([0-9,]{4,8})", text)
    duration = re.search(r"(\d+h\s*\d*m|\d+\s*hrs?\s*\d*\s*mins?)", text, re.I)
    fn = re.search(r"\b([A-Z]{2}\d{3,4})\b", text)
    stops = ("Non-stop" if re.search(r"non.?stop|direct|0 stop", text, re.I)
             else ("1 Stop" if re.search(r"1 stop", text, re.I) else ""))

    airlines = ["IndiGo", "Air India", "SpiceJet", "Vistara",
                "Akasa", "AirAsia", "Go First", "GoAir"]
    airline = next((a for a in airlines if a.lower() in text.lower()), "Unknown")

    if not times:
        return None

    price_str = f"₹{int(price.group(1).replace(',','')):,}" if price else "N/A"
    return {
        "index": index,
        "airline": airline,
        "flight_number": fn.group(1) if fn else "",
        "departure_time": times[0] if len(times) > 0 else "",
        "arrival_time": times[1] if len(times) > 1 else "",
        "duration": duration.group(1) if duration else "",
        "price": price_str,
        "stops": stops,
    }


def _parse_flights_from_body_text(text: str) -> list[dict]:
    """Parse flight-like rows from full visible page text."""
    if not text or len(text) < 80:
        return []

    times = list(re.finditer(r"\b\d{1,2}:\d{2}(?:\s*[AP]M)?\b", text, re.I))
    if len(times) < 2:
        return []

    flights = []
    for i in range(min(len(times) - 1, 20)):
        start = max(0, times[i].start() - 120)
        end = min(len(text), times[i + 1].end() + 180)
        segment = text[start:end]
        parsed = _parse_card_text(segment, len(flights))
        if parsed and parsed.get("price") != "N/A":
            flights.append(parsed)
        if len(flights) >= 10:
            break

    # Re-index after filtering.
    for i, flight in enumerate(flights):
        flight["index"] = i
    return flights
