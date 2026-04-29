"""
Test script to verify the application handles incomplete and complete inputs correctly
"""

import asyncio
import sys
sys.path.insert(0, '/Users/sriram/aeroo/backend')

from agents.planner_agent import PlannerAgent

def test_incomplete_queries():
    """Test incomplete queries that should ask clarification questions"""
    planner = PlannerAgent()

    print("=" * 70)
    print("TESTING INCOMPLETE QUERIES")
    print("=" * 70)

    incomplete_queries = [
        "flight to Delhi",           # Missing origin
        "from Hyderabad",            # Missing destination
        "Delhi to Mumbai",           # Missing date (will use default)
        "Bangalore",                 # Only one city
    ]

    for query in incomplete_queries:
        print(f"\n📝 Query: '{query}'")
        result = planner.parse_query(query)
        print(f"✓ Valid: {result['valid']}")
        print(f"  Complete: {result.get('complete', 'N/A')}")

        if not result['valid']:
            print(f"  ❌ Error: {result.get('error', 'N/A')}")
            clarification = result.get('clarification_questions', [])
            if clarification:
                print(f"  ❓ Questions needed ({len(clarification)}):")
                for q in clarification:
                    print(f"     - {q['question']}")
                    if q.get('examples'):
                        print(f"       Examples: {', '.join(q['examples'][:3])}")


def test_complete_queries():
    """Test complete queries that should work immediately"""
    planner = PlannerAgent()

    print("\n\n" + "=" * 70)
    print("TESTING COMPLETE QUERIES")
    print("=" * 70)

    complete_queries = [
        "I want to fly from Hyderabad to Delhi tomorrow",
        "from Mumbai to Bangalore on 15th May",
        "Delhi to Goa next Friday",
        "from Pune to Jaipur today",
        "Hyderabad → Chennai on 20/05/2025",
    ]

    for query in complete_queries:
        print(f"\n📝 Query: '{query}'")
        result = planner.parse_query(query)
        print(f"✓ Valid: {result['valid']}")
        print(f"  Complete: {result.get('complete', 'N/A')}")

        if result['valid']:
            parsed = result['parsed']
            print(f"  ✅ Origin: {parsed['origin']['display']} ({parsed['origin']['code']})")
            print(f"  ✅ Destination: {parsed['destination']['display']} ({parsed['destination']['code']})")
            print(f"  ✅ Date: {parsed['date']}")
            print(f"  ✅ Passengers: {parsed['passengers']}")
            print(f"  ✅ Class: {parsed['class']}")


def test_clarification_flow():
    """Test the clarification flow"""
    planner = PlannerAgent()

    print("\n\n" + "=" * 70)
    print("TESTING CLARIFICATION FLOW")
    print("=" * 70)

    # Start with incomplete query
    initial_query = "I need a flight to Delhi"
    print(f"\n1️⃣  Initial query: '{initial_query}'")
    result1 = planner.parse_query(initial_query)
    print(f"   Valid: {result1['valid']}")

    if not result1['valid']:
        clarification = result1.get('clarification_questions', [])
        print(f"   Need {len(clarification)} clarification(s)")
        for q in clarification:
            print(f"   ❓ {q['question']}")

    # Add clarification
    clarification_response = "from Hyderabad tomorrow"
    combined = f"{initial_query} {clarification_response}"
    print(f"\n2️⃣  Combined query: '{combined}'")
    result2 = planner.parse_query(combined)
    print(f"   Valid: {result2['valid']}")

    if result2['valid']:
        parsed = result2['parsed']
        print(f"   ✅ Origin: {parsed['origin']['display']}")
        print(f"   ✅ Destination: {parsed['destination']['display']}")
        print(f"   ✅ Date: {parsed['date']}")


if __name__ == "__main__":
    test_incomplete_queries()
    test_complete_queries()
    test_clarification_flow()

    print("\n\n" + "=" * 70)
    print("✅ ALL TESTS COMPLETED")
    print("=" * 70)
