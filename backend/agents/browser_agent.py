"""
Browser Agent
Playwright-powered automation agent that operates a visible browser.
Implements human-like delays, retry logic, and popup handling.
"""

import asyncio
import random
import base64
from typing import Optional, Callable
from urllib.parse import quote

from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from utils.logger import AgentLogger


class BrowserAgent:
    """
    Browser automation agent using Playwright in visible (non-headless) mode.
    Handles navigation, input, clicks, popups, and screenshots.
    """

    # MakeMyTrip selectors (with fallbacks)
    SELECTORS = {
        "one_way_tab": [
            "li[data-cy='oneWay']",
            "label[for='oneWay']",
            ".oneway-tab",
            "//span[contains(text(),'One Way')]",
        ],
        "origin_input": [
            "[data-cy='fromCity']",
            "#fromCity",
            ".form_field-origin input",
            "input[placeholder*='From']",
            "input[placeholder*='from']",
            ".hsw_input-origin",
        ],
        "destination_input": [
            "[data-cy='toCity']",
            "#toCity",
            ".form_field-destination input",
            "input[placeholder*='To']",
            "input[placeholder*='to']",
            ".hsw_input-destination",
        ],
        "date_input": [
            "[data-cy='departure']",
            "#journeyDate",
            ".form_field--date input",
            "input[placeholder*='Departure']",
        ],
        "search_button": [
            "[data-cy='search']",
            "button.primaryBtn",
            "a.btn-search",
            "//button[contains(text(),'Search')]",
            "//a[contains(text(),'Search')]",
            ".fli-search-btn",
            ".search-btn",
        ],
        "popup_close": [
            ".modal-close",
            ".close-btn",
            "[aria-label='Close']",
            ".commonModal__close",
            ".login-modal .close",
            "button.closeModalBtn",
            ".login-modal__close",
            "[data-cy='closeModal']",
            ".ILModal .icon-cancel",
        ],
        "flight_result": [
            ".listingCard",
            ".flt-info",
            ".flight-card",
            ".air-itinerary",
            "[data-cy='flightCard']",
            ".fliCard",
            ".resultsUi",
        ],
    }

    def __init__(self, on_screenshot: Optional[Callable] = None, on_log: Optional[Callable] = None):
        self.logger = AgentLogger("browser")
        self.on_screenshot = on_screenshot
        self.on_log = on_log
        self.playwright = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._running = False

    async def launch(self):
        """Launch the visible browser"""
        self.logger.info("Launching visible browser...")
        await self._log("info", "Launching Chromium browser in visible mode")
        
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(
            headless=False,
            args=[
                "--no-sandbox",
                "--disable-infobars",
                "--start-maximized",
            ],
            slow_mo=50,
        )
        
        self.context = await self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        
        self.page = await self.context.new_page()
        self._running = True
        
        # Start screenshot loop
        asyncio.create_task(self._screenshot_loop())
        
        self.logger.success("Browser launched successfully")
        await self._log("success", "Browser launched and ready")

    async def close(self):
        """Close the browser"""
        self._running = False
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        self.logger.info("Browser closed")

    async def navigate(self, url: str):
        """Navigate to a URL"""
        await self._log("info", f"Navigating to: {url}")
        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as e:
            self.logger.warning(f"Navigation error or timeout: {e}")
            await self._log("warning", "Page load timed out or had an error, proceeding anyway")
        await self._human_delay(3.0, 5.0)
        await self._take_screenshot()
        await self._log("success", f"Loaded: {url}")

    async def close_popups(self):
        """Intelligently close any popups, modals, or cookie banners"""
        await self._log("info", "Scanning for popups and overlays...")
        closed = 0
        
        for attempt in range(3):
            await asyncio.sleep(1.0)
            
            for selector in self.SELECTORS["popup_close"]:
                try:
                    # In flaky network / half-loaded DOM states, some Playwright calls can hang.
                    # Keep popup handling bounded so the workflow can continue.
                    elements = await asyncio.wait_for(
                        self.page.query_selector_all(selector),
                        timeout=2.5,
                    )
                    for el in elements:
                        try:
                            visible = await asyncio.wait_for(el.is_visible(), timeout=1.5)
                        except Exception:
                            visible = False

                        if visible:
                            await el.click(timeout=2000)
                            await asyncio.sleep(0.5)
                            closed += 1
                            await self._log("info", f"Closed popup via: {selector}")
                except Exception:
                    pass
            
            # Try pressing Escape
            try:
                await asyncio.wait_for(self.page.keyboard.press("Escape"), timeout=2.0)
                await asyncio.sleep(0.5)
            except Exception:
                pass
            
            # Remove overlay divs via JS
            try:
                removed = await asyncio.wait_for(self.page.evaluate("""
                    () => {
                        let count = 0;
                        const selectors = [
                            '.modal-overlay', '.ILModal-overlay', '.overlay',
                            '[class*="modal-backdrop"]', '[class*="overlay"]',
                            '.login-modal', '.hsw-login-modal',
                        ];
                        selectors.forEach(sel => {
                            document.querySelectorAll(sel).forEach(el => {
                                if (el.style.display !== 'none') {
                                    el.style.display = 'none';
                                    count++;
                                }
                            });
                        });
                        // Remove body overflow hidden
                        document.body.style.overflow = '';
                        document.documentElement.style.overflow = '';
                        return count;
                    }
                """), timeout=2.5)
                if removed > 0:
                    await self._log("info", f"Removed {removed} overlay elements via JS")
                    closed += removed
            except Exception:
                pass
        
        if closed > 0:
            await self._log("success", f"Cleared {closed} popup/overlay elements")
        else:
            await self._log("info", "No popups detected")
        
        await self._take_screenshot()

    async def click_one_way(self):
        """Click the One Way tab"""
        await self._log("info", "Selecting one-way trip option...")
        
        success = await self._try_selectors_click(self.SELECTORS["one_way_tab"])
        if not success:
            # Try text-based click
            try:
                await self.page.get_by_text("One Way", exact=True).first.click(timeout=3000)
                success = True
            except Exception:
                pass
        
        if success:
            await self._human_delay(0.5, 1.0)
            await self._log("success", "One Way selected")
        else:
            await self._log("warning", "Could not click One Way tab - may already be selected")
        
        await self._take_screenshot()

    async def fill_origin(self, city: str):
        """Fill origin city with autocomplete handling"""
        await self._log("info", f"Entering origin city: {city}")
        
        success = False
        try:
            # Open the input modal manually (MakeMyTrip specific)
            btn = await self.page.query_selector("[data-cy='fromCity']") or await self.page.query_selector("#fromCity")
            if btn:
                await btn.click(timeout=3000)
                await asyncio.sleep(1.0)
            
            input_el = await self.page.query_selector("input[placeholder*='From']") or await self.page.query_selector("input[placeholder*='from']") or await self.page.query_selector(".react-autosuggest__input")
            if input_el:
                await input_el.fill("")
                await self._type_human(input_el, city)
                await asyncio.sleep(1.5)
                if await self._select_autocomplete(city):
                    success = True
        except Exception:
            pass
            
        if not success:
            self.logger.warning("Falling back to standard selectors for origin")
            for selector in self.SELECTORS["origin_input"]:
                try:
                    el = await self.page.wait_for_selector(selector, timeout=2000)
                    if el:
                        await el.click(timeout=2000)
                        await asyncio.sleep(0.5)
                        try:
                            await el.fill("")
                        except:
                            pass
                        await self._type_human(el, city)
                        await asyncio.sleep(1.0)
                        if await self._select_autocomplete(city):
                            success = True
                            break
                except Exception:
                    continue
        
        if not success:
            await self._log("warning", f"Origin input not found via selectors, trying vision fallback")
        
        await self._take_screenshot()

    async def fill_destination(self, city: str):
        """Fill destination city with autocomplete handling"""
        await self._log("info", f"Entering destination city: {city}")
        
        success = False
        try:
            # Open the input modal manually (MakeMyTrip specific)
            btn = await self.page.query_selector("[data-cy='toCity']") or await self.page.query_selector("#toCity")
            if btn:
                await btn.click(timeout=3000)
                await asyncio.sleep(1.0)
            
            input_el = await self.page.query_selector("input[placeholder*='To']") or await self.page.query_selector("input[placeholder*='to']") or await self.page.query_selector(".react-autosuggest__input")
            if input_el:
                await input_el.fill("")
                await self._type_human(input_el, city)
                await asyncio.sleep(1.5)
                if await self._select_autocomplete(city):
                    success = True
        except Exception:
            pass

        if not success:
            self.logger.warning("Falling back to standard selectors for destination")
            for selector in self.SELECTORS["destination_input"]:
                try:
                    el = await self.page.wait_for_selector(selector, timeout=2000)
                    if el:
                        await el.click(timeout=2000)
                        await asyncio.sleep(0.5)
                        try:
                            await el.fill("")
                        except:
                            pass
                        await self._type_human(el, city)
                        await asyncio.sleep(1.0)
                        if await self._select_autocomplete(city):
                            success = True
                            break
                except Exception:
                    continue
        
        if not success:
            await self._log("warning", "Destination input not found via selectors")
        
        await self._take_screenshot()

    async def fill_date(self, date_str: str):
        """Fill the travel date"""
        await self._log("info", f"Selecting travel date: {date_str}")
        
        # Parse date
        parts = date_str.split("/")
        if len(parts) == 3:
            day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
        else:
            await self._log("warning", "Invalid date format")
            return
        
        # Click date input
        for selector in self.SELECTORS["date_input"]:
            try:
                el = await self.page.wait_for_selector(selector, timeout=3000)
                if el:
                    await el.click()
                    await asyncio.sleep(0.8)
                    break
            except Exception:
                continue

        # Fast path: MakeMyTrip DayPicker often exposes exact `aria-label` per day cell.
        # Try clicking the target date directly before doing any month navigation.
        try:
            from datetime import date as _date
            import calendar as _cal

            dt = _date(year, month, day)
            # Example aria-label: "Tue Apr 21 2026"
            weekday = _cal.day_abbr[dt.weekday()]
            month_abbr = _cal.month_abbr[month]
            aria = f"{weekday} {month_abbr} {day} {year}"

            direct = self.page.locator(
                f"[aria-label='{aria}']:not(.DayPicker-Day--disabled):not(.DayPicker-Day--outside)"
            ).first
            if await direct.count() > 0:
                await direct.click(timeout=4000)
                await self._log("success", f"Selected date via aria-label: {aria}")
                await self._human_delay(0.3, 0.7)
                await self._take_screenshot()
                return
        except Exception:
            pass
        
        # Navigate calendar to correct month and click date
        try:
            await asyncio.wait_for(
                self._navigate_calendar_and_click(day, month, year),
                timeout=20.0,
            )
        except Exception:
            await self._log(
                "warning",
                "Date picker interaction timed out; falling back to typing date",
            )
            # Fallback: type date directly into input if visible
            try:
                date_str2 = f"{day:02d}/{month:02d}/{year}"
                for sel in self.SELECTORS["date_input"]:
                    try:
                        el = await self.page.query_selector(sel)
                        if el:
                            await el.fill(date_str2)
                            break
                    except Exception:
                        pass
            except Exception:
                pass
        
        await self._human_delay(0.5, 1.0)
        await self._take_screenshot()

    async def click_search(self):
        """Click the search flights button"""
        await self._log("info", "Clicking Search Flights button...")
        
        success = await self._try_selectors_click(self.SELECTORS["search_button"])
        
        if not success:
            # Try JS click as last resort
            try:
                await self.page.evaluate("""
                    () => {
                        const btns = Array.from(document.querySelectorAll('button, a'));
                        const searchBtn = btns.find(b => 
                            b.textContent.toLowerCase().includes('search') &&
                            (b.className.toLowerCase().includes('search') || b.type === 'submit')
                        );
                        if (searchBtn) { searchBtn.click(); return true; }
                        return false;
                    }
                """)
                success = True
            except Exception:
                pass
        
        if success:
            await self._log("success", "Search clicked, waiting for results...")
        else:
            await self._log("error", "Could not find Search button")
        
        await self._take_screenshot()

    async def navigate_results_direct(self, origin_code: str, destination_code: str, date_str: str):
        """Open results page directly when UI search submission is flaky."""
        try:
            day, month, year = [int(x) for x in date_str.split("/")]
            itinerary = f"{origin_code.lower()}-{destination_code.lower()}-{day:02d}/{month:02d}/{year}"
            url = (
                "https://www.makemytrip.com/flight/search"
                f"?itinerary={quote(itinerary, safe='')}"
                "&tripType=O&paxType=A-1_C-0_I-0&intl=false&cabinClass=E"
            )
            await self._log("info", f"Fallback navigation to results URL: {url}")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2.0)
            await self._take_screenshot()
            return True
        except Exception as e:
            await self._log("warning", "Direct results navigation failed", {"error": str(e)})
            return False

    async def wait_for_results(self):
        """Wait for flight results to load"""
        await self._log("info", "Waiting for flight results to load...")
        
        result_selectors = [
            ".listingCard",
            ".flt-info",
            ".flight-card",
            ".air-itinerary",
            "[data-cy='flightCard']",
            ".fliCard",
            "[data-cy*='flight']",
            "[class*='listingCard']",
            "[class*='fliCard']",
            "[class*='flightCard']",
            "[id*='flightCard']",
        ]
        
        loaded = False
        for i in range(30):  # Wait up to 30 seconds
            await asyncio.sleep(1.0)

            # Trigger lazy-load / hydration
            try:
                await self.page.evaluate(
                    "() => window.scrollTo(0, Math.min(document.body.scrollHeight, 1400))"
                )
            except Exception:
                pass

            for selector in result_selectors:
                try:
                    count = await self.page.locator(selector).count()
                    if count > 0:
                        loaded = True
                        await self._log("success", f"Found {count} flight result elements")
                        break
                except Exception:
                    pass
            if i % 5 == 4:
                await self._log("info", "Still waiting for results page to render...")
                await self._take_screenshot()
            if loaded:
                break
        
        if not loaded:
            # Heuristic fallback: results pages sometimes render different card classes
            # while still exposing clear "price + time" text patterns.
            try:
                text_probe = await self.page.evaluate(
                    "() => (document.body?.innerText || '').toLowerCase().slice(0, 12000)"
                )
                if ("sort by" in text_probe or "flights found" in text_probe) and "₹" in text_probe:
                    loaded = True
                    await self._log(
                        "info",
                        "Detected results page via text heuristics despite selector mismatch",
                    )
            except Exception:
                pass

        if not loaded:
            # Capture quick diagnostic so we can see what the page is showing.
            try:
                diag = await self.page.evaluate(
                    "() => ({url: location.href, title: document.title, text: (document.body?.innerText || '').slice(0, 600)})"
                )
                await self._log(
                    "warning",
                    "Flight results not detected; page may be blocked or still rendering",
                    diag,
                )
            except Exception:
                await self._log("warning", "Flight results may not have loaded correctly")
        
        # Wait for page to stabilize
        await asyncio.sleep(2.0)
        await self._take_screenshot()
        return loaded

    async def extract_flights_from_dom(self, max_cards: int = 25) -> list:
        """Extract visible flight cards directly from the live DOM."""
        try:
            cards = await self.page.evaluate(
                """(maxCards) => {
                    const selectors = [
                        "[data-cy='flightCard']",
                        ".fliCard",
                        ".listingCard",
                        "[class*='flightCard']",
                        "[class*='fliCard']",
                        "[class*='listingCard']",
                    ];

                    let elements = [];
                    for (const sel of selectors) {
                        const found = Array.from(document.querySelectorAll(sel));
                        if (found.length) {
                            elements = found;
                            break;
                        }
                    }

                    const rows = [];
                    for (const el of elements.slice(0, maxCards)) {
                        const text = (el.innerText || "").replace(/\\s+/g, " ").trim();
                        if (!text || text.length < 20) continue;
                        rows.push(text);
                    }
                    return rows;
                }""",
                max_cards,
            )
            return cards or []
        except Exception:
            return []

    async def get_page_html(self) -> str:
        """Get the full page HTML for extraction"""
        return await self.page.content()

    async def get_screenshot(self) -> bytes:
        """Take a screenshot of the current page"""
        try:
            return await self.page.screenshot(type="jpeg", quality=75, timeout=5000)
        except Exception:
            return b""

    async def click_flight_at_index(self, index: int):
        """Click on a specific flight result"""
        await self._log("info", f"Clicking flight at index {index}...")
        
        for selector in self.SELECTORS["flight_result"]:
            try:
                elements = await self.page.query_selector_all(selector)
                if index < len(elements):
                    await elements[index].scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    await elements[index].click()
                    await self._log("success", f"Clicked flight {index + 1}")
                    await self._human_delay(1.5, 2.5)
                    await self._take_screenshot()
                    return True
            except Exception:
                continue
        
        return False

    async def click_flight_by_details(self, flight: dict) -> bool:
        """Find and click a flight matching the given details (airline & departure time)."""
        await self._log("info", f"Looking for {flight.get('airline')} departing at {flight.get('departure_time')}")
        
        target_airline = (flight.get("airline") or "").lower()
        target_dep = (flight.get("departure_time") or "").lower()
        
        for selector in self.SELECTORS["flight_result"]:
            try:
                elements = await self.page.query_selector_all(selector)
                for i, el in enumerate(elements):
                    text = (await el.inner_text() or "").lower()
                    if not text.strip():
                        continue
                    
                    airline_match = not target_airline or any(word in text for word in target_airline.split() if len(word) > 2)
                    
                    dep_match = False
                    if target_dep:
                        if target_dep in text or target_dep.replace(":", "") in text:
                            dep_match = True
                        elif target_dep.startswith("0") and target_dep[1:] in text:
                            dep_match = True
                    else:
                        dep_match = True
                    
                    if airline_match and dep_match:
                        await self._log("success", f"Matched flight card {i + 1}")
                        await el.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                        
                        btn = await el.query_selector("button")
                        if btn:
                            await btn.click()
                        else:
                            await el.click()
                            
                        await self._human_delay(1.5, 2.5)
                        await self._take_screenshot()
                        return True
            except Exception:
                continue
        
        idx = flight.get("index", 0)
        await self._log("warning", f"Could not precisely match flight text. Falling back to index {idx + 1}")
        return await self.click_flight_at_index(idx)

    async def fill_passenger_form(self, passenger: dict):
        """Fill passenger details form"""
        await self._log("info", f"Filling passenger details for {passenger.get('first_name', '')} {passenger.get('last_name', '')}")
        
        field_mapping = {
            "first_name": [
                "input[placeholder*='First']",
                "input[name*='firstName']",
                "input[id*='firstName']",
                "#pax_fname_0",
            ],
            "last_name": [
                "input[placeholder*='Last']",
                "input[name*='lastName']",
                "input[id*='lastName']",
                "#pax_lname_0",
            ],
            "age": [
                "input[name*='age']",
                "input[placeholder*='Age']",
                "input[id*='age']",
            ],
        }
        
        for field_name, selectors in field_mapping.items():
            value = str(passenger.get(field_name, ""))
            if not value:
                continue
            
            for selector in selectors:
                try:
                    el = await self.page.wait_for_selector(selector, timeout=2000)
                    if el:
                        await el.click()
                        await el.fill("")
                        await self._type_human(el, value)
                        await self._log("info", f"Filled {field_name}: {value}")
                        break
                except Exception:
                    continue
        
        # Handle gender selection
        gender = passenger.get("gender", "male").lower()
        gender_selectors = {
            "male": ["input[value='M']", "input[value='Male']", "#male", ".gender-male"],
            "female": ["input[value='F']", "input[value='Female']", "#female", ".gender-female"],
        }
        
        if gender in gender_selectors:
            for sel in gender_selectors[gender]:
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        await el.click()
                        break
                except Exception:
                    pass
        
        await self._take_screenshot()
        await self._log("success", "Passenger details filled")

    # ─── Private Helpers ─────────────────────────────────────────────────────

    async def _try_selectors_click(self, selectors: list) -> bool:
        """Try multiple selectors and click the first visible one"""
        for selector in selectors:
            try:
                if selector.startswith("//"):
                    el = await self.page.wait_for_selector(f"xpath={selector}", timeout=2000)
                else:
                    el = await self.page.wait_for_selector(selector, timeout=2000)
                
                if el and await el.is_visible():
                    await el.scroll_into_view_if_needed()
                    await asyncio.sleep(0.2)
                    await el.click(timeout=3000)
                    return True
            except Exception:
                continue
        return False

    async def _type_human(self, element, text: str):
        """Type text with human-like random delays between keystrokes"""
        for char in text:
            await element.type(char, delay=random.randint(50, 150))
            if random.random() < 0.1:
                await asyncio.sleep(random.uniform(0.1, 0.3))

    async def _select_autocomplete(self, city: str):
        """Select from autocomplete dropdown"""
        autocomplete_selectors = [
            ".react-autosuggest__suggestion",
            ".autoSuggestItem",
            ".ui-autocomplete li",
            ".dropdown-item",
            ".suggestion-item",
            f"li[data-value*='{city}']",
            f"[data-city='{city}']",
            ".autoSuggestMenu li",
            ".autosuggest-list li",
        ]
        
        for selector in autocomplete_selectors:
            try:
                await asyncio.sleep(0.5)
                items = await self.page.query_selector_all(selector)
                for item in items[:3]:
                    text = await item.text_content() or ""
                    if city.lower() in text.lower():
                        await item.click()
                        await self._log("info", f"Selected autocomplete: {text.strip()}")
                        return True
            except Exception:
                continue
        
        # Fallback: press Enter and hope for the best
        await self.page.keyboard.press("Enter")
        return False

    async def _navigate_calendar_and_click(self, day: int, month: int, year: int):
        """Navigate date picker to target month and click day"""
        import calendar
        
        MONTH_NAMES = [
            "", "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        
        target_month_str = f"{MONTH_NAMES[month]} {year}"
        
        # Navigate months if needed (bounded; don't get stuck on DOM changes)
        for _ in range(12):
            header = None
            try:
                header = await asyncio.wait_for(
                    self.page.query_selector(
                        ".DayPicker-Caption, .react-datepicker__current-month, .calendar-header"
                    ),
                    timeout=2.0,
                )
            except Exception:
                header = None

            if header:
                try:
                    header_text = await asyncio.wait_for(header.text_content(), timeout=2.0) or ""
                except Exception:
                    header_text = ""

                if target_month_str.lower() in header_text.lower():
                    break

            # Click next month arrow
            next_btns = [
                ".DayPicker-NavButton--next",
                ".react-datepicker__navigation--next",
                "button[aria-label='Next Month']",
                ".calendar-next",
            ]
            clicked = False
            for btn_sel in next_btns:
                try:
                    btn = await asyncio.wait_for(self.page.query_selector(btn_sel), timeout=1.5)
                    if btn:
                        await btn.click()
                        await asyncio.sleep(0.4)
                        clicked = True
                        break
                except Exception:
                    pass

            if not clicked:
                break
        
        # Click the specific day
        day_selectors = [
            f".DayPicker-Day:not(.DayPicker-Day--disabled):not(.DayPicker-Day--outside)[aria-label*='{day}']",
            f"[data-day='{day}']",
            f".react-datepicker__day:not(.react-datepicker__day--disabled)",
        ]
        
        for sel in day_selectors:
            try:
                days = await self.page.query_selector_all(sel)
                for d in days:
                    text = (await d.text_content() or "").strip()
                    if text == str(day):
                        await d.click()
                        return True
            except Exception:
                continue
        
        # Fallback: type date directly into input if visible
        try:
            date_str = f"{day:02d}/{month:02d}/{year}"
            for sel in self.SELECTORS["date_input"]:
                try:
                    el = await self.page.query_selector(sel)
                    if el:
                        await el.fill(date_str)
                        return True
                except Exception:
                    pass
        except Exception:
            pass
        
        return False

    async def _screenshot_loop(self):
        """Continuously capture and send screenshots"""
        while self._running:
            try:
                if self.page and not self.page.is_closed():
                    if not await self._is_page_visibly_ready():
                        await asyncio.sleep(1.0)
                        continue
                    screenshot = await self.page.screenshot(type="jpeg", quality=60, timeout=5000)
                    if self.on_screenshot and screenshot:
                        await self.on_screenshot(screenshot)
            except Exception:
                pass
            await asyncio.sleep(1.5)

    async def _take_screenshot(self):
        """Take a one-off screenshot and send it"""
        try:
            if self.page and not self.page.is_closed():
                if not await self._is_page_visibly_ready():
                    return
                screenshot = await self.page.screenshot(type="jpeg", quality=70, timeout=5000)
                if self.on_screenshot and screenshot:
                    await self.on_screenshot(screenshot)
        except Exception:
            pass

    async def _human_delay(self, min_s: float = 0.5, max_s: float = 1.5):
        """Random human-like delay"""
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _is_page_visibly_ready(self) -> bool:
        """Avoid pushing transient blank/white frames to frontend."""
        try:
            probe = await self.page.evaluate(
                """() => {
                    const body = document.body;
                    const text = (body?.innerText || "").trim();
                    const hasMainNodes = !!document.querySelector(
                      "main, #root, #app, [data-cy='flightCard'], .fliCard, .listingCard, form"
                    );
                    return { textLen: text.length, hasMainNodes };
                }"""
            )
            return bool(probe.get("hasMainNodes") or probe.get("textLen", 0) > 40)
        except Exception:
            return True

    async def _log(self, level: str, message: str, details: dict = None):
        """Send log via callback"""
        if self.on_log:
            await self.on_log(level, message, details)
        self.logger.info(f"[{level}] {message}")
