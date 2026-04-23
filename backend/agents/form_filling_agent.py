"""
Form Filling Agent
Automates passenger detail entry in the MakeMyTrip booking form.
Stops execution before reaching the payment page.
"""

import asyncio
from utils.logger import AgentLogger


PAYMENT_PAGE_INDICATORS = [
    "payment", "pay now", "card details", "debit card", "credit card",
    "net banking", "upi", "wallet", "cvv", "card number", "expiry",
    "secure payment", "pay ₹", "complete booking", "confirm and pay",
]


class FormFillingAgent:
    """
    Form Filling Agent: Fills passenger information in booking forms
    and detects when the payment page is reached to stop automation.
    """

    def __init__(self):
        self.logger = AgentLogger("form_filling")

    async def fill_and_detect_payment(
        self, browser_agent, passenger: dict
    ) -> dict:
        """
        Fill passenger details and detect if we've hit the payment page.
        Returns: {"stopped_before_payment": bool, "page_type": str}
        """
        page = browser_agent.page

        if not page:
            return {"stopped_before_payment": False, "error": "No page available"}

        await self._emit_browser_progress(
            browser_agent,
            "info",
            "Preparing passenger form automation...",
            take_screenshot=True,
        )

        # Check if we're already on payment page
        if await self._is_payment_page(page):
            self.logger.warning("Already on payment page - stopping!")
            await self._emit_browser_progress(
                browser_agent,
                "warning",
                "Payment page detected before filling passenger details; stopping automation",
                take_screenshot=True,
            )
            return {"stopped_before_payment": True, "page_type": "payment"}

        # Fill passenger details
        await self._ensure_traveller_form_visible(browser_agent, page)
        await self._fill_traveller_form(browser_agent, passenger)

        # Check again after filling
        if await self._is_payment_page(page):
            return {"stopped_before_payment": True, "page_type": "payment"}

        return {"stopped_before_payment": False, "page_type": "booking_form"}

    async def _fill_traveller_form(self, browser_agent, passenger: dict):
        """Fill the traveller details section"""
        page = browser_agent.page

        self.logger.info("Filling traveller details...")
        await self._emit_browser_progress(
            browser_agent,
            "info",
            "Started filling traveller details on booking form",
            take_screenshot=True,
        )

        # Title/Salutation
        gender = passenger.get("gender", "male").lower()
        title = "Mr" if gender == "male" else "Ms"

        title_selectors = [
            f"select[name*='title'] option[value='{title}']",
            f"li[data-value='{title}']",
            f".title-selector [value='{title}']",
        ]

        for sel in title_selectors:
            try:
                el = await page.query_selector(sel)
                if el:
                    await el.click()
                    await self._emit_browser_progress(
                        browser_agent,
                        "info",
                        f"Selected title: {title}",
                        take_screenshot=True,
                    )
                    break
            except Exception:
                pass

        # First Name
        await self._fill_field(
            browser_agent,
            page,
            [
                "input[placeholder*='First']",
                "input[name*='firstName']",
                "input[id*='firstName']",
                "#pax-fname",
                "#pax_fname_0",
                "input[id*='fname']",
                "input[name*='fname']",
                "input[data-cy*='first']",
            ],
            passenger.get("first_name", "")
        )

        # Last Name
        await self._fill_field(
            browser_agent,
            page,
            [
                "input[placeholder*='Last']",
                "input[name*='lastName']",
                "input[id*='lastName']",
                "#pax-lname",
                "#pax_lname_0",
                "input[id*='lname']",
                "input[name*='lname']",
                "input[data-cy*='last']",
            ],
            passenger.get("last_name", "")
        )

        # Age (some forms ask for DOB instead)
        age = passenger.get("age")
        if age:
            # Try direct age field
            age_filled = await self._fill_field(
                browser_agent,
                page,
                [
                    "input[name*='age']",
                    "input[id*='age']",
                    "input[placeholder*='Age']",
                ],
                str(age),
                required=False
            )

            # If no age field, try DOB fields
            if not age_filled:
                await self._fill_dob_from_age(page, int(age))
                await self._emit_browser_progress(
                    browser_agent,
                    "info",
                    "Filled date of birth fields using age fallback",
                    take_screenshot=True,
                )

        # Email
        email = passenger.get("email", "")
        if email:
            await self._fill_field(
                browser_agent,
                page,
                [
                    "input[type='email']",
                    "input[name*='email']",
                    "input[id*='email']",
                    "input[placeholder*='Email']",
                ],
                email,
                required=False
            )

        # Phone
        phone = passenger.get("phone", "")
        if phone:
            await self._fill_field(
                browser_agent,
                page,
                [
                    "input[type='tel']",
                    "input[name*='phone']",
                    "input[id*='phone']",
                    "input[placeholder*='Phone']",
                    "input[placeholder*='Mobile']",
                ],
                phone,
                required=False
            )

        # Gender radio buttons
        await self._select_gender(browser_agent, page, gender)

        self.logger.success("Traveller form filled successfully")
        await self._emit_browser_progress(
            browser_agent,
            "success",
            "Traveller form fields filled successfully",
            take_screenshot=True,
        )

    async def _ensure_traveller_form_visible(self, browser_agent, page):
        """Bring traveller form into view by clicking common continue/book CTAs."""
        probe_selectors = [
            "input[placeholder*='First']",
            "input[name*='firstName']",
            "input[id*='firstName']",
            "input[id*='fname']",
            "input[name*='fname']",
        ]
        for sel in probe_selectors:
            try:
                el = await page.query_selector(sel)
                if el and await el.is_visible():
                    return
            except Exception:
                pass

        await self._emit_browser_progress(
            browser_agent,
            "info",
            "Passenger form not visible yet; trying to open traveller details section",
            take_screenshot=True,
        )

        cta_selectors = [
            "button:has-text('BOOK NOW')",
            "button:has-text('Book Now')",
            "button:has-text('Continue')",
            "button:has-text('PROCEED')",
            "a:has-text('BOOK NOW')",
            "a:has-text('Continue')",
            "[data-cy*='book']",
            "[data-cy*='continue']",
        ]

        for sel in cta_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.count() > 0 and await btn.is_visible():
                    await btn.click(timeout=2500)
                    await asyncio.sleep(1.2)
                    await self._emit_browser_progress(
                        browser_agent,
                        "info",
                        f"Clicked traveller-form CTA: {sel}",
                        take_screenshot=True,
                    )
            except Exception:
                continue

            for probe in probe_selectors:
                try:
                    pe = await page.query_selector(probe)
                    if pe and await pe.is_visible():
                        await self._emit_browser_progress(
                            browser_agent,
                            "success",
                            "Traveller form is now visible",
                            take_screenshot=True,
                        )
                        return
                except Exception:
                    pass

    async def _fill_field(
        self,
        browser_agent,
        page,
        selectors: list,
        value: str,
        required: bool = True,
    ) -> bool:
        """Fill a form field by trying multiple selectors"""
        if not value:
            return False

        for selector in selectors:
            try:
                el = await page.wait_for_selector(selector, timeout=5000)
                if el and await el.is_visible():
                    try:
                        await el.scroll_into_view_if_needed(timeout=1500)
                    except Exception:
                        pass
                    await el.click()
                    await el.fill("")

                    # Type character by character for human feel
                    for char in value:
                        await el.type(char)
                        await asyncio.sleep(0.05)

                    self.logger.info(f"Filled field '{selector}' with value")
                    field_name = self._infer_field_name(selectors)
                    await self._emit_browser_progress(
                        browser_agent,
                        "info",
                        f"Filled {field_name} field",
                        {"selector": selector},
                        take_screenshot=True,
                    )
                    return True
            except Exception:
                continue

        # Fallback: infer fields by semantic keywords in labels/placeholders/ids.
        field_name = self._infer_field_name(selectors)
        keywords = self._field_keywords(field_name)
        if keywords:
            fallback = await self._fill_by_keywords(page, keywords, value)
            if fallback:
                await self._emit_browser_progress(
                    browser_agent,
                    "info",
                    f"Filled {field_name} field via semantic fallback",
                    {"keywords": keywords},
                    take_screenshot=True,
                )
                return True

        if required:
            self.logger.warning(f"Could not fill required field. Tried: {selectors}")
            await self._emit_browser_progress(
                browser_agent,
                "warning",
                "Could not fill a required passenger field with current selectors",
                {"tried_selectors": selectors},
                take_screenshot=True,
            )
        return False

    async def _select_gender(self, browser_agent, page, gender: str):
        """Select gender radio button"""
        selectors = {
            "male": [
                "input[type='radio'][value='M']",
                "input[type='radio'][value='Male']",
                "input[type='radio'][value='MALE']",
                "#gender-male",
                ".gender-male input",
            ],
            "female": [
                "input[type='radio'][value='F']",
                "input[type='radio'][value='Female']",
                "input[type='radio'][value='FEMALE']",
                "#gender-female",
                ".gender-female input",
            ],
        }

        for sel in selectors.get(gender, []):
            try:
                el = await page.query_selector(sel)
                if el:
                    await el.click()
                    self.logger.info(f"Selected gender: {gender}")
                    await self._emit_browser_progress(
                        browser_agent,
                        "info",
                        f"Selected gender: {gender}",
                        {"selector": sel},
                        take_screenshot=True,
                    )
                    return
            except Exception:
                pass

    async def _fill_dob_from_age(self, page, age: int):
        """Fill date of birth fields based on age"""
        from datetime import datetime

        birth_year = datetime.now().year - age
        birth_month = "01"
        birth_day = "01"

        dob_selectors = {
            "day": ["select[name*='dobDay']", "input[name*='dobDay']"],
            "month": ["select[name*='dobMonth']", "input[name*='dobMonth']"],
            "year": [
                "select[name*='dobYear']",
                "input[name*='dobYear']",
                "input[placeholder*='Year']",
            ],
        }

        values = {"day": birth_day, "month": birth_month, "year": str(birth_year)}

        for field, selectors in dob_selectors.items():
            for sel in selectors:
                try:
                    el = await page.query_selector(sel)
                    if el:
                        tag = await el.evaluate("el => el.tagName.toLowerCase()")
                        if tag == "select":
                            await el.select_option(value=values[field])
                        else:
                            await el.fill(values[field])
                        break
                except Exception:
                    pass

    async def _is_payment_page(self, page) -> bool:
        """Detect if the current page is a payment page"""
        try:
            # Check URL
            url = page.url.lower()
            if any(keyword in url for keyword in ["payment", "pay", "checkout"]):
                return True

            # Check page text
            text = await asyncio.wait_for(
                page.evaluate(
                    """() => {
                        const bodyText = (document.body?.innerText || "").toLowerCase();
                        return bodyText.slice(0, 60000);
                    }"""
                ),
                timeout=8.0,
            )

            payment_indicators_found = sum(
                1 for indicator in PAYMENT_PAGE_INDICATORS
                if indicator in text
            )

            # If 3+ payment indicators found, it's likely the payment page
            if payment_indicators_found >= 3:
                self.logger.warning(
                    f"Payment page detected! Found {payment_indicators_found} indicators"
                )
                return True

        except asyncio.TimeoutError:
            self.logger.warning("Payment page detection timed out; proceeding with form fill")
        except Exception:
            pass

        return False

    def _infer_field_name(self, selectors: list) -> str:
        joined = " ".join(selectors).lower()
        if "first" in joined or "fname" in joined:
            return "first name"
        if "last" in joined or "lname" in joined:
            return "last name"
        if "email" in joined:
            return "email"
        if "phone" in joined or "mobile" in joined or "tel" in joined:
            return "phone"
        if "age" in joined:
            return "age"
        return "passenger"

    def _field_keywords(self, field_name: str) -> list:
        mapping = {
            "first name": ["first", "fname", "given", "traveller first", "adult first"],
            "last name": ["last", "lname", "surname", "family", "traveller last", "adult last"],
            "email": ["email", "e-mail", "mail"],
            "phone": ["phone", "mobile", "contact", "tel"],
            "age": ["age", "years"],
        }
        return mapping.get(field_name, [])

    async def _fill_by_keywords(self, page, keywords: list, value: str) -> bool:
        try:
            handle = await page.evaluate_handle(
                """(keywords) => {
                    const norm = (s) => (s || "").toLowerCase();
                    const inputs = Array.from(document.querySelectorAll("input, textarea"))
                        .filter((el) => {
                            const type = norm(el.getAttribute("type"));
                            if (["hidden", "submit", "button", "checkbox", "radio"].includes(type)) return false;
                            const style = window.getComputedStyle(el);
                            if (style.display === "none" || style.visibility === "hidden") return false;
                            const rect = el.getBoundingClientRect();
                            return rect.width > 2 && rect.height > 2;
                        });

                    const scoreFor = (el) => {
                        const attrs = [
                            el.getAttribute("placeholder"),
                            el.getAttribute("name"),
                            el.getAttribute("id"),
                            el.getAttribute("aria-label"),
                            el.getAttribute("data-cy"),
                            el.getAttribute("data-testid"),
                            el.getAttribute("autocomplete"),
                            el.closest("label")?.innerText,
                            el.parentElement?.innerText,
                        ].map(norm).join(" ");
                        let score = 0;
                        for (const k of keywords) {
                            if (attrs.includes(norm(k))) score += 1;
                        }
                        return score;
                    };

                    let best = null;
                    let bestScore = 0;
                    for (const el of inputs) {
                        const score = scoreFor(el);
                        if (score > bestScore) {
                            best = el;
                            bestScore = score;
                        }
                    }
                    return bestScore > 0 ? best : null;
                }""",
                keywords,
            )
            el = handle.as_element() if handle else None
            if not el:
                return False
            await el.click()
            await el.fill("")
            for char in value:
                await el.type(char)
                await asyncio.sleep(0.04)
            return True
        except Exception:
            return False

    async def _emit_browser_progress(
        self,
        browser_agent,
        level: str,
        message: str,
        details: dict = None,
        take_screenshot: bool = False,
    ):
        """Push form-filling updates to live UI logs and screenshot stream."""
        try:
            await browser_agent._log(level, message, details or {})
        except Exception:
            pass

        if take_screenshot:
            try:
                await browser_agent._take_screenshot()
            except Exception:
                pass
