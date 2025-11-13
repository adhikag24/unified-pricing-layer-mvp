#!/usr/bin/env python3
"""
Debug script to test multi-instance payables.
Simulates emitting redemption events and inspects database.
"""
import sys
import os
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.storage.database import Database
from src.ingestion.pipeline import IngestionPipeline

def main():
    # Use test database
    db = Database("data/debug_multi_instance.db")
    db.connect()
    db.initialize_schema()

    pipeline = IngestionPipeline(db)

    # Load and emit the three events
    events_dir = Path(__file__).parent / "sample_events" / "supplier_and_payable_event" / "ttd-passes-prod-1322884534"

    event_files = [
        "001-booking-confirmed.json",
        "002-redemption-1.json",
        "003-redemption-2.json"
    ]

    print("=" * 80)
    print("EMITTING EVENTS")
    print("=" * 80)

    for filename in event_files:
        filepath = events_dir / filename
        print(f"\n📤 Emitting: {filename}")

        with open(filepath) as f:
            event_data = json.load(f)

        result = pipeline.ingest_event(event_data)
        print(f"   Result: {result.success} - {result.message}")
        if result.details:
            print(f"   Details: {result.details}")

    print("\n" + "=" * 80)
    print("DATABASE INSPECTION")
    print("=" * 80)

    # Check supplier_timeline table
    print("\n📋 SUPPLIER_TIMELINE table:")
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT order_detail_id, supplier_timeline_version, fulfillment_instance_id,
               status, amount, amount_basis
        FROM supplier_timeline
        WHERE order_id = '1322884534'
        ORDER BY supplier_timeline_version
    """)

    rows = cursor.fetchall()
    print(f"\nFound {len(rows)} rows:")
    for row in rows:
        print(f"  v{row['supplier_timeline_version']}: fulfillment_instance_id={row['fulfillment_instance_id']}, "
              f"status={row['status']}, amount={row['amount']}, amount_basis={row['amount_basis']}")

    # Check supplier_payable_lines table
    print("\n📋 SUPPLIER_PAYABLE_LINES table:")
    cursor.execute("""
        SELECT supplier_timeline_version, fulfillment_instance_id,
               party_type, obligation_type, amount, amount_effect
        FROM supplier_payable_lines
        WHERE order_id = '1322884534'
        ORDER BY supplier_timeline_version
    """)

    rows = cursor.fetchall()
    print(f"\nFound {len(rows)} rows:")
    for row in rows:
        print(f"  v{row['supplier_timeline_version']}: fulfillment_instance_id={row['fulfillment_instance_id']}, "
              f"{row['party_type']}/{row['obligation_type']}, amount={row['amount']} ({row['amount_effect']})")

    # Check payables query result
    print("\n" + "=" * 80)
    print("GET_TOTAL_EFFECTIVE_PAYABLES() RESULT")
    print("=" * 80)

    payables = db.get_total_effective_payables("1322884534")
    print(f"\nReturned {len(payables)} payable instance(s):")

    for idx, payable in enumerate(payables, 1):
        print(f"\n#{idx}: order_detail_id={payable['order_detail_id']}")
        print(f"     fulfillment_instance_id: {payable['fulfillment_instance_id']}")
        print(f"     supplier_reference_id: {payable['supplier_reference_id']}")
        print(f"     Baseline: {payable['supplier_baseline']['amount']} ({payable['supplier_baseline']['status']})")
        print(f"     Parties: {len(payable['parties'])}")

        for party in payable['parties']:
            party_label = f"{party['party_type']}: {party['party_name']}"
            print(f"       - {party_label}")
            print(f"         Baseline: {party['baseline']}")
            print(f"         Adjustment: {party['total_adjustment']}")
            print(f"         Total Payable: {party['total_payable']}")
            print(f"         Obligations: {len(party['obligations'])}")
            for obl in party['obligations']:
                print(f"           * {obl['obligation_type']}: {obl['amount']} ({obl['amount_effect']})")

        print(f"     TOTAL PAYABLE: {payable['total_payable']}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total payable instances: {len(payables)}")
    print(f"Expected: 3 (1 booking + 2 redemptions)")

    if len(payables) == 3:
        print("✅ PASS: Correct number of instances!")

        # Check fulfillment_instance_ids
        fulfillment_ids = [p['fulfillment_instance_id'] for p in payables]
        print(f"\nFulfillment Instance IDs: {fulfillment_ids}")

        expected_ids = [None, "ticket_code_1757809185001", "ticket_code_1757809307001"]
        if set(fulfillment_ids) == set(expected_ids):
            print("✅ PASS: Correct fulfillment_instance_id values!")
        else:
            print(f"❌ FAIL: Expected {expected_ids}")
    else:
        print("❌ FAIL: Incorrect number of instances!")
        print("This means payables are NOT splitting correctly by fulfillment_instance_id")

    print("\n")

if __name__ == "__main__":
    main()
