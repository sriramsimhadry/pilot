"""
Test script to verify clarification handling for incomplete queries
"""

import sys
sys.path.insert(0, '/Users/sriram/aeroo/backend')

from agents.planner_agent import PlannerAgent

def test_complete_query():
    """Test with complete input: source, destination, date"""
    print("\n" + "="*70)
    print("TEST 1: Complete Query (source, destination, date)")
    print("="*70)

    planner = PlannerAgent()

    # Test case 1: Complete query
    query = "I want to fly from Hyderabad to Delhi tomorrow"
    result = planner.parse_query(query)

    print(f"Query: {query}")
    print(f"Valid: {result['valid']}")
    print(f"Complete: {result.get('complete', 'N/A')}")

    if result['valid']:
        parsed = result['parsed']
        print(f"Origin: {parsed['origin']['display']}")
        print(f"Destination: {parsed['destination']['display']}")
        print(f"Date: {parsed['date']}")
        print(f"✅ PASS: Complete query processed successfully")
    else:
        print(f"❌ FAIL: Valid query marked as invalid")

    return result['valid']


def test_incomplete_query_no_destination():
    """Test with incomplete input: only source"""
    print("\n" + "="*70)
    print("TEST 2: Incomplete Query (source only, missing destination)")
    print("="*70)

    planner = PlannerAgent()

    query = "I want to fly from Hyderabad tomorrow"
    result = planner.parse_query(query)

    print(f"Query: {query}")
    print(f"Valid: {result['valid']}")
    print(f"Complete: {result.get('complete', 'N/A')}")

    if not result['valid']:
        print(f"Error: {result.get('error', 'N/A')}")

        clarifications = result.get('clarification_questions', [])
        if clarifications:
            print(f"✅ Clarification questions generated: {len(clarifications)}")
            for i, q in enumerate(clarifications, 1):
                print(f"  Q{i} ({q['type']}): {q['question']}")
                if q.get('examples'):
                    print(f"       Examples: {', '.join(q['examples'][:5])}")
            print(f"✅ PASS: Incomplete query triggers clarification")
            return True
        else:
            print(f"❌ FAIL: No clarification questions generated")
            return False
    else:
        print(f"❌ FAIL: Incomplete query marked as valid")
        return False


def test_incomplete_query_no_source():
    """Test with incomplete input: only destination"""
    print("\n" + "="*70)
    print("TEST 3: Incomplete Query (destination only, missing source)")
    print("="*70)

    planner = PlannerAgent()

    query = "I want to go to Mumbai next week"
    result = planner.parse_query(query)

    print(f"Query: {query}")
    print(f"Valid: {result['valid']}")

    if not result['valid']:
        clarifications = result.get('clarification_questions', [])
        if clarifications:
            print(f"✅ Clarification questions generated: {len(clarifications)}")
            for q in clarifications:
                print(f"  - {q['type']}: {q['question']}")
            print(f"✅ PASS: Incomplete query triggers clarification")
            return True
        else:
            print(f"❌ FAIL: No clarification questions generated")
            return False
    else:
        print(f"❌ FAIL: Incomplete query marked as valid")
        return False


def test_minimal_query():
    """Test with minimal input: just cities"""
    print("\n" + "="*70)
    print("TEST 4: Minimal Query (just cities, no date)")
    print("="*70)

    planner = PlannerAgent()

    query = "Bangalore to Chennai"
    result = planner.parse_query(query)

    print(f"Query: {query}")
    print(f"Valid: {result['valid']}")

    if result['valid']:
        parsed = result['parsed']
        print(f"Origin: {parsed['origin']['display']}")
        print(f"Destination: {parsed['destination']['display']}")
        print(f"Date: {parsed['date']} (auto-set to tomorrow)")
        print(f"✅ PASS: Minimal query works with default date")
        return True
    else:
        print(f"❌ FAIL: Valid minimal query marked as invalid")
        return False


def test_complex_complete_query():
    """Test with complex complete query"""
    print("\n" + "="*70)
    print("TEST 5: Complex Complete Query (with passengers, class, return)")
    print("="*70)

    planner = PlannerAgent()

    query = "I need 2 passengers, business class, round trip from Delhi to Goa, leaving 15th May and returning 20th May"
    result = planner.parse_query(query)

    print(f"Query: {query}")
    print(f"Valid: {result['valid']}")

    if result['valid']:
        parsed = result['parsed']
        print(f"Origin: {parsed['origin']['display']}")
        print(f"Destination: {parsed['destination']['display']}")
        print(f"Passengers: {parsed['passengers']}")
        print(f"Class: {parsed['class']}")
        print(f"Round Trip: {parsed['is_round_trip']}")
        print(f"✅ PASS: Complex query parsed successfully")
        return True
    else:
        print(f"❌ FAIL: Complex valid query marked as invalid")
        print(f"Error: {result.get('error', 'N/A')}")
        return False


def test_vague_query():
    """Test with vague query that needs clarification"""
    print("\n" + "="*70)
    print("TEST 6: Vague Query (needs multiple clarifications)")
    print("="*70)

    planner = PlannerAgent()

    query = "I want to book a flight"
    result = planner.parse_query(query)

    print(f"Query: {query}")
    print(f"Valid: {result['valid']}")

    if not result['valid']:
        clarifications = result.get('clarification_questions', [])
        print(f"Clarification questions needed: {len(clarifications)}")
        if clarifications:
            for i, q in enumerate(clarifications, 1):
                print(f"  Q{i}: {q['question']}")
            print(f"✅ PASS: Vague query triggers multiple clarifications")
            return True
        else:
            print(f"❌ FAIL: No clarification questions generated")
            return False
    else:
        print(f"❌ FAIL: Vague query marked as valid")
        return False


def run_all_tests():
    """Run all tests and report results"""
    print("\n\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█  TESTING AEROO APPLICATION - CLARIFICATION HANDLING" + " "*14 + "█")
    print("█" + " "*68 + "█")
    print("█"*70)

    tests = [
        test_complete_query,
        test_incomplete_query_no_destination,
        test_incomplete_query_no_source,
        test_minimal_query,
        test_complex_complete_query,
        test_vague_query,
    ]

    results = []
    for test in tests:
        try:
            results.append(test())
        except Exception as e:
            print(f"\n❌ ERROR in test: {e}")
            import traceback
            traceback.print_exc()
            results.append(False)

    # Summary
    print("\n\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█  TEST SUMMARY" + " "*54 + "█")
    print("█" + " "*68 + "█")
    print("█"*70)

    passed = sum(results)
    total = len(results)

    print(f"\nTests Passed: {passed}/{total}")
    print(f"Pass Rate: {(passed/total)*100:.1f}%")

    if passed == total:
        print("\n✅ ALL TESTS PASSED - Application handles incomplete inputs correctly!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed - See details above")

    print("\n" + "█"*70 + "\n")

    return passed == total


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
