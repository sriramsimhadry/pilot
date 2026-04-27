"""
Analysis Agent
Analyzes a list of flights using Groq LLM and returns a structured
top-3 recommendation with reasons and booking suggestions.
"""

import os
import json
import re
from typing import Optional

from utils.logger import AgentLogger

try:
    from groq import Groq as GroqClient
    _GROQ_AVAILABLE = True
except ImportError:
    _GROQ_AVAILABLE = False


class AnalysisAgent:
    def __init__(self):
        self.logger = AgentLogger("analysis")
        groq_key = os.getenv("GROQ_API_KEY", "")
        self.groq_client = None

        if _GROQ_AVAILABLE and groq_key:
            try:
                self.groq_client = GroqClient(api_key=groq_key)
                self.logger.info("Groq client initialized for flight analysis")
            except Exception as e:
                self.logger.warning(f"Failed to initialize Groq client: {e}")
        else:
            self.logger.warning("Groq not available. Analysis will be skipped.")

    def analyze_flights(self, flights: list) -> Optional[dict]:
        """
        Send up to 20 flights to Groq LLM and get a structured recommendation.

        Returns a dict like:
        {
            "overall_summary": "...",
            "top3": [
                {
                    "rank": 1,
                    "airline": "IndiGo",
                    "flight_number": "6E-456",
                    "reason": "Best balance of price and short duration...",
                    "best_price_tip": "Slightly cheaper on Cleartrip than MakeMyTrip today.",
                    "book_on": ["MakeMyTrip", "Cleartrip"]
                },
                ...
            ]
        }
        Or None if analysis fails / Groq not available.
        """
        if not self.groq_client or not flights:
            return None

        self.logger.info("Analyzing flights with Groq LLM...")

        try:
            # Use all provided flights up to 20
            top_flights = flights[:20]
            flight_data = json.dumps(top_flights, indent=2)

            system_prompt = (
                "You are an expert AI travel analyst. You will receive a JSON list of flight options.\n"
                "Your task:\n"
                "1. Identify the TOP 3 best flights based on a smart balance of: price, duration, stops, and departure convenience.\n"
                "2. For each top pick, write a concise reason (1-2 sentences) explaining WHY it is recommended.\n"
                "3. For each top pick, provide a 'best_price_tip' — a practical tip on where to book it for the best price "
                "(e.g., 'Book directly on IndiGo.com to avoid convenience fees', or 'Check Cleartrip for a ₹200 discount today').\n"
                "4. For each top pick, list 2-3 booking platforms from: ['MakeMyTrip', 'Cleartrip', 'EaseMyTrip', 'Airline Direct', 'Ixigo'].\n\n"
                "IMPORTANT: Respond ONLY with valid JSON in EXACTLY this format (no markdown, no code fences, no extra text):\n"
                "{\n"
                '  "overall_summary": "One sentence summarising why these 3 were chosen from the full set.",\n'
                '  "top3": [\n'
                "    {\n"
                '      "rank": 1,\n'
                '      "airline": "<airline name>",\n'
                '      "flight_number": "<flight number or null>",\n'
                '      "reason": "<why this flight is recommended>",\n'
                '      "best_price_tip": "<booking tip>",\n'
                '      "book_on": ["<site1>", "<site2>"]\n'
                "    }\n"
                "  ]\n"
                "}"
            )

            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyse these flights and give me the top 3:\n{flight_data}"},
                ],
                temperature=0.2,
                max_tokens=900,
            )

            raw = response.choices[0].message.content.strip()
            self.logger.info("Groq response received — parsing JSON...")

            # Strip markdown fences if the model wraps in ```json ... ```
            raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"\s*```$", "", raw, flags=re.MULTILINE)

            result = json.loads(raw)

            # Validate expected keys
            if "top3" not in result or not isinstance(result["top3"], list):
                raise ValueError("Response missing 'top3' array")

            self.logger.info(f"Flight analysis complete — {len(result['top3'])} recommendations generated.")
            return result

        except json.JSONDecodeError as e:
            self.logger.error(f"Groq returned invalid JSON: {e}. Raw: {raw[:300]}")
            # Fallback: return the raw text wrapped in a simple structure
            return {
                "overall_summary": raw[:500],
                "top3": [],
                "_raw": True,
            }
        except Exception as e:
            self.logger.error(f"Error during LLM analysis: {e}")
            return None
