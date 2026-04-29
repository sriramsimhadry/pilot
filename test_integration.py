"""
Integration test to verify clarification handling in the complete workflow
"""

import asyncio
import sys
sys.path.insert(0, '/Users/sriram/aeroo/backend')

from agents.workflow_orchestrator import WorkflowOrchestrator
from utils.connection_manager import ConnectionManager
from utils.logger import AgentLogger


class MockWebSocket:
    """Mock WebSocket for testing"""
    def __init__(self):
        self.messages = []

    async def send_text(self, data):
        self.messages.append(data)


class TestConnectionManager(ConnectionManager):
    """Test version that captures messages"""
    def __init__(self):
        super().__init__()
        self.captured_messages = {}

    async def send_message(self, workflow_id: str, message: dict):
        """Override to capture messages"""
        if workflow_id not in self.captured_messages:
            self.captured_messages[workflow_id] = []
        self.captured_messages[workflow_id].append(message)
        # Also call parent to maintain normal behavior
        await super().send_message(workflow_id, message)


async def test_incomplete_query_workflow():
    """Test incomplete query handling in workflow"""
    print("\n" + "="*70)
    print("INTEGRATION TEST: Incomplete Query Workflow")
    print("="*70)

    # Setup
    workflow_id = "test-workflow-001"
    manager = TestConnectionManager()

    # Create mock WebSocket
    mock_ws = MockWebSocket()
    await manager.connect(mock_ws, workflow_id)

    # Create orchestrator
    orchestrator = WorkflowOrchestrator(
        workflow_id=workflow_id,
        connection_manager=manager
    )

    # Test 1: Incomplete query
    print("\n[STAGE 1] Submitting incomplete query...")
    query = "i want to go to mumbai"
    print(f"Query: '{query}'")

    # Run workflow with incomplete query
    await orchestrator.run(query=query)

    # Check results
    status = orchestrator.get_status()
    print(f"\nWorkflow Status: {status['stage']}")
    print(f"Is awaiting clarification: {orchestrator._awaiting_clarification}")
    print(f"Plan valid: {orchestrator.plan.get('valid')}")

    # Check messages sent
    messages = manager.captured_messages.get(workflow_id, [])
    print(f"\nMessages sent to client: {len(messages)}")

    clarification_msgs = [m for m in messages if m.get('type') == 'clarification']
    if clarification_msgs:
        print(f"\n✅ Clarification message found!")
        clarification = clarification_msgs[0]['payload']
        questions = clarification.get('questions', [])
        print(f"Number of questions: {len(questions)}")
        for i, q in enumerate(questions, 1):
            print(f"  Q{i} ({q['type']}): {q['question']}")
            if q.get('examples'):
                print(f"       Examples: {', '.join(q['examples'][:3])}")
    else:
        print(f"\n❌ No clarification message found!")
        print("Messages received:")
        for msg in messages:
            print(f"  - {msg.get('type')}: {msg.get('payload', {}).get('stage', 'N/A')}")

    # Test 2: Provide clarification
    print("\n" + "-"*70)
    print("[STAGE 2] Providing clarification...")
    clarification_response = "from Delhi"
    print(f"Clarification: '{clarification_response}'")

    await orchestrator.provide_clarification(clarification_response)

    # Check updated status
    status = orchestrator.get_status()
    print(f"\nUpdated workflow status: {status['stage']}")
    print(f"Is awaiting clarification: {orchestrator._awaiting_clarification}")
    print(f"Plan valid: {orchestrator.plan.get('valid')}")

    if orchestrator.plan.get('valid'):
        parsed = orchestrator.plan.get('parsed', {})
        print(f"\n✅ Plan now valid!")
        print(f"  Origin: {parsed.get('origin', {}).get('display')}")
        print(f"  Destination: {parsed.get('destination', {}).get('display')}")
        print(f"  Date: {parsed.get('date')}")
        return True
    else:
        # Still need clarification
        error = orchestrator.plan.get('error')
        questions = orchestrator.plan.get('clarification_questions', [])
        if questions:
            print(f"\n⚠️  Still need more clarification:")
            for q in questions:
                print(f"  - {q['question']}")
        return False


async def test_complete_query_workflow():
    """Test complete query handling in workflow"""
    print("\n\n" + "="*70)
    print("INTEGRATION TEST: Complete Query Workflow")
    print("="*70)

    workflow_id = "test-workflow-002"
    manager = TestConnectionManager()
    orchestrator = WorkflowOrchestrator(
        workflow_id=workflow_id,
        connection_manager=manager
    )

    print("\n[STAGE 1] Submitting complete query...")
    query = "I want to fly from Delhi to Mumbai tomorrow"
    print(f"Query: '{query}'")

    await orchestrator.run(query=query)

    status = orchestrator.get_status()
    print(f"\nWorkflow Status: {status['stage']}")
    print(f"Is awaiting clarification: {orchestrator._awaiting_clarification}")
    print(f"Plan valid: {orchestrator.plan.get('valid')}")

    if orchestrator.plan.get('valid'):
        parsed = orchestrator.plan.get('parsed', {})
        print(f"\n✅ Plan valid and workflow started!")
        print(f"  Origin: {parsed.get('origin', {}).get('display')}")
        print(f"  Destination: {parsed.get('destination', {}).get('display')}")
        print(f"  Date: {parsed.get('date')}")

        # Check if flights were extracted (or queued)
        flights = status.get('flights', [])
        print(f"  Flights found: {len(flights) if flights else 'Extraction in progress'}")
        return True
    else:
        print(f"\n❌ Plan invalid - this should not happen!")
        print(f"Error: {orchestrator.plan.get('error')}")
        return False


async def main():
    print("\n\n" + "█"*70)
    print("█" + " "*68 + "█")
    print("█  AEROO INTEGRATION TESTS - CLARIFICATION WORKFLOW" + " "*17 + "█")
    print("█" + " "*68 + "█")
    print("█"*70)

    results = []

    try:
        results.append(await test_incomplete_query_workflow())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(False)

    try:
        results.append(await test_complete_query_workflow())
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
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
    print(f"\nIntegration Tests Passed: {passed}/{total}")
    print(f"Pass Rate: {(passed/total)*100:.1f}%")

    if passed == total:
        print("\n✅ ALL INTEGRATION TESTS PASSED!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")

    print("\n" + "█"*70 + "\n")
    return passed == total


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
