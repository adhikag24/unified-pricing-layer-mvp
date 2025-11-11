"""
End-to-End Test Script for Supplier Lifecycle v2 Multi-Party Structure

Tests all 4 scenarios:
1. Scenario A: Issued → Effective Payables Includes All Parties
2. Scenario B: Issued → Cancelled → Affiliate Obligations Carried Forward (Projection)
3. Scenario C: Issued → Cancelled → Partner Penalty Persists
4. Scenario D: Issued → Cancelled with Adjusted Affiliate

Run this script to validate the complete implementation.
"""

import json
import os
from datetime import datetime
from src.storage.database import Database
from src.ingestion.pipeline import IngestionPipeline


def load_sample_event(filename):
    """Load sample event from file"""
    filepath = os.path.join("sample_events/supplier_v2", filename)
    with open(filepath, 'r') as f:
        event = json.load(f)
    # Update timestamp
    event["emitted_at"] = datetime.utcnow().isoformat()
    return event


def print_section(title):
    """Print formatted section header"""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80)


def print_payables(payables):
    """Print formatted payables breakdown"""
    for detail in payables:
        print(f"\n📦 Order Detail: {detail['order_detail_id']}")
        baseline = detail['supplier_baseline']
        print(f"   Supplier: {baseline['supplier_id']} | Status: {baseline['status']}")
        print(f"   Baseline: {baseline['amount']} {baseline['currency']}", end="")
        if baseline.get('amount_basis'):
            print(f" ({baseline['amount_basis']})", end="")
        print()
        print(f"   Reason: {baseline['reason']}")

        if detail['party_obligations']:
            print(f"\n   Party Obligations:")
            for obl in detail['party_obligations']:
                effect_symbol = "🔺" if obl['amount_effect'] == 'INCREASES_PAYABLE' else "🔻"
                print(f"     {effect_symbol} {obl['obligation_type']}: {obl['amount']} {obl['currency']} ({obl['amount_effect']})")
                print(f"        Party: {obl['party_name']} (ID: {obl['party_id']})")

        print(f"\n   💰 Total Payable: {detail['total_payable']} {baseline['currency']}")
        print("   " + "-" * 76)


def test_scenario_a():
    """
    Scenario A: Issued → Effective Payables Includes All Parties

    Expected Outcome:
    - Baseline: 300000 IDR (gross)
    - Supplier commission retention: -45000 IDR (DECREASES_PAYABLE)
    - Affiliate commission: +4694 IDR (INCREASES_PAYABLE)
    - VAT on affiliate: +516 IDR (INCREASES_PAYABLE)
    - Total: 300000 - 45000 + 4694 + 516 = 260210 IDR
    """
    print_section("SCENARIO A: Issued with Multi-Party Obligations")

    # Setup
    db = Database(":memory:")
    db.connect()
    db.initialize_schema()
    pipeline = IngestionPipeline(db)

    # Emit v1: Issued with parties
    event = load_sample_event("1_issued_with_parties.json")
    result = pipeline.ingest_event(event)

    print(f"✅ Ingestion: {result.message}")
    print(f"   Details: {result.details}")

    # Query payables
    payables = db.get_total_effective_payables("ORD-9001")
    print_payables(payables)

    # Validate
    assert len(payables) == 1, "Should have 1 order_detail"
    detail = payables[0]
    assert detail['supplier_baseline']['amount'] == 300000, "Baseline should be 300000"
    assert detail['supplier_baseline']['amount_basis'] == "gross", "Basis should be gross"
    assert len(detail['party_obligations']) == 3, "Should have 3 party obligations"

    # Validate amount_effect logic
    expected_total = 300000 - 45000 + 4694 + 516  # 260210
    assert detail['total_payable'] == expected_total, f"Total should be {expected_total}, got {detail['total_payable']}"

    print("\n✅ SCENARIO A PASSED: All party obligations included with correct amount_effect")
    return db


def test_scenario_b():
    """
    Scenario B: Issued → Cancelled → Affiliate Carried Forward (Projection)

    Expected Outcome:
    v1: Same as Scenario A (260210 IDR total)
    v2: Cancelled with empty parties array
    - Baseline: 50000 IDR (cancellation fee)
    - Affiliate obligations EXCLUDED (timeline-linked, version >= 1)
    - Total: 50000 IDR
    """
    print_section("SCENARIO B: Cancelled with Projection (Empty Parties Array)")

    # Setup
    db = Database(":memory:")
    db.connect()
    db.initialize_schema()
    pipeline = IngestionPipeline(db)

    # Emit v1: Issued with parties
    event_v1 = load_sample_event("1_issued_with_parties.json")
    result_v1 = pipeline.ingest_event(event_v1)
    print(f"✅ v1 Ingestion: {result_v1.message}")

    # Emit v2: Cancelled with fee, NO parties array
    event_v2 = load_sample_event("2_cancelled_with_fee_no_parties.json")
    result_v2 = pipeline.ingest_event(event_v2)
    print(f"✅ v2 Ingestion: {result_v2.message}")

    # Query payables (should show v2 with cancelled status)
    payables = db.get_total_effective_payables("ORD-9001")
    print_payables(payables)

    # Validate
    detail = payables[0]
    assert detail['supplier_baseline']['status'] == "CancelledWithFee", "Status should be CancelledWithFee"
    assert detail['supplier_baseline']['amount'] == 50000, "Baseline should be cancellation fee (50000)"
    assert len(detail['party_obligations']) == 0, "Should have NO party obligations (timeline excluded)"
    assert detail['total_payable'] == 50000, "Total should be baseline only (50000)"

    print("\n✅ SCENARIO B PASSED: Projection correctly excludes timeline obligations on cancellation")
    return db


def test_scenario_c():
    """
    Scenario C: Issued → Cancelled → Partner Penalty Persists

    Expected Outcome:
    v1: Issued (260210 IDR)
    v2: Cancelled (50000 IDR baseline, timeline excluded)
    v3: Partner Penalty (standalone, version = -1)
    - Baseline: 50000 IDR
    - Affiliate penalty: +500000 IDR (INCREASES_PAYABLE, version = -1)
    - Total: 50000 + 500000 = 550000 IDR
    """
    print_section("SCENARIO C: Standalone Partner Penalty Persists After Cancellation")

    # Setup
    db = Database(":memory:")
    db.connect()
    db.initialize_schema()
    pipeline = IngestionPipeline(db)

    # Emit v1: Issued with parties
    event_v1 = load_sample_event("1_issued_with_parties.json")
    pipeline.ingest_event(event_v1)
    print("✅ v1: Issued")

    # Emit v2: Cancelled with fee
    event_v2 = load_sample_event("2_cancelled_with_fee_no_parties.json")
    pipeline.ingest_event(event_v2)
    print("✅ v2: Cancelled")

    # Emit partner adjustment (version = -1)
    event_penalty = load_sample_event("4_affiliate_penalty.json")
    result_penalty = pipeline.ingest_event(event_penalty)
    print(f"✅ Partner Adjustment: {result_penalty.message}")

    # Query payables
    payables = db.get_total_effective_payables("ORD-9001")
    print_payables(payables)

    # Validate
    detail = payables[0]
    assert detail['supplier_baseline']['status'] == "CancelledWithFee", "Status should be CancelledWithFee"
    assert len(detail['party_obligations']) == 1, "Should have 1 standalone obligation (penalty)"

    penalty_obl = detail['party_obligations'][0]
    assert penalty_obl['obligation_type'] == "AFFILIATE_PENALTY", "Should be AFFILIATE_PENALTY"
    assert penalty_obl['amount'] == 500000, "Penalty amount should be 500000"
    assert penalty_obl['amount_effect'] == "INCREASES_PAYABLE", "Should increase payable"

    expected_total = 50000 + 500000  # 550000
    assert detail['total_payable'] == expected_total, f"Total should be {expected_total}"

    print("\n✅ SCENARIO C PASSED: Standalone penalty persists regardless of supplier status")
    return db


def test_scenario_d():
    """
    Scenario D: Issued → Cancelled with Adjusted Affiliate

    Expected Outcome:
    v1: Issued (original affiliate commission based on booking)
    v2: Cancelled with UPDATED parties array (affiliate adjusted to cancellation fee basis)
    - Baseline: 75000 IDR (cancellation fee)
    - Timeline obligations EXCLUDED (version >= 1 from v1)
    - NEW obligations from v2 parties array (latest wins):
      - Affiliate commission: +2000 IDR (adjusted, INCREASES_PAYABLE)
      - VAT: +220 IDR (INCREASES_PAYABLE)
    - Total: 75000 + 2000 + 220 = 77220 IDR
    """
    print_section("SCENARIO D: Cancelled with Adjusted Affiliate Obligations")

    # Setup
    db = Database(":memory:")
    db.connect()
    db.initialize_schema()
    pipeline = IngestionPipeline(db)

    # Note: Using ORD-9002 for this scenario
    # Emit v1: Issued (we'll create a simple one inline)
    event_v1 = {
        "event_id": "evt_issued_v1_ord9002",
        "event_type": "SupplierLifecycleEvent",
        "schema_version": "supplier.timeline.v2",
        "order_id": "ORD-9002",
        "order_detail_id": "OD-002",
        "emitted_at": datetime.utcnow().isoformat(),
        "supplier": {
            "status": "ISSUED",
            "supplier_id": "AGODA",
            "amount_due": 350000,
            "amount_basis": "gross",
            "currency": "IDR"
        },
        "parties": [
            {
                "party_type": "AFFILIATE",
                "party_id": "100005361",
                "party_name": "Partner CFD",
                "lines": [
                    {
                        "obligation_type": "AFFILIATE_COMMISSION",
                        "amount": 5000,
                        "amount_effect": "INCREASES_PAYABLE",
                        "currency": "IDR"
                    }
                ]
            }
        ]
    }
    pipeline.ingest_event(event_v1)
    print("✅ v1: Issued with original affiliate commission (5000)")

    # Emit v2: Cancelled with adjusted affiliate
    event_v2 = load_sample_event("3_cancelled_with_adjusted_affiliate.json")
    result_v2 = pipeline.ingest_event(event_v2)
    print(f"✅ v2: {result_v2.message}")

    # Query payables
    payables = db.get_total_effective_payables("ORD-9002")
    print_payables(payables)

    # Validate
    detail = payables[0]
    assert detail['supplier_baseline']['status'] == "CancelledWithFee", "Status should be CancelledWithFee"
    assert detail['supplier_baseline']['amount'] == 75000, "Baseline should be 75000"

    # Should have 2 obligations from v2 (latest wins, v1 excluded by timeline filtering)
    assert len(detail['party_obligations']) == 2, f"Should have 2 obligations from v2, got {len(detail['party_obligations'])}"

    affiliate_comm = next(o for o in detail['party_obligations'] if o['obligation_type'] == 'AFFILIATE_COMMISSION')
    assert affiliate_comm['amount'] == 2000, "Affiliate commission should be adjusted to 2000"

    expected_total = 75000 + 2000 + 220  # 77220
    assert detail['total_payable'] == expected_total, f"Total should be {expected_total}, got {detail['total_payable']}"

    print("\n✅ SCENARIO D PASSED: Latest obligations win via party-level projection")
    return db


def run_all_tests():
    """Run all test scenarios"""
    print("\n" + "🧪" * 40)
    print("  COMPREHENSIVE END-TO-END TEST SUITE")
    print("  Multi-Party Supplier Lifecycle v2")
    print("🧪" * 40)

    try:
        test_scenario_a()
        test_scenario_b()
        test_scenario_c()
        test_scenario_d()

        print("\n" + "✅" * 40)
        print("  ALL TESTS PASSED!")
        print("  Multi-party structure with amount_effect working correctly")
        print("✅" * 40 + "\n")

        return True
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        import traceback
        traceback.print_exc()
        return False
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
