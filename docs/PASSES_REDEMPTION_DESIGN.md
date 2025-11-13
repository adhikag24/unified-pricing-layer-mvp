# Fulfillment-Triggered Payables Design (Passes Vertical)

## Problem Statement

The **Passes** vertical has a unique business model where:
- **1 order_id** + **1 order_detail_id** = Multiple visit passes (e.g., 3 playground visits)
- **Customer pays upfront** for all passes at purchase time
- **Supplier payables are generated over time** as each pass is redeemed (not at purchase)
- **Redemption timeline** can span weeks/months (e.g., playground valid 2025-09-12 to 2025-09-28)

### Current Data Pattern (from sample)

**Order**: `1322884534` | **Order Detail**: `1359185528`
- **3 entertainment bookings** (3 separate redemption events)
- **Single upfront payment**: 3 × 138,000 IDR = 414,000 IDR
- **Redemption timeline**:
  - Booking 1: Redeemed 2025-09-13 06:20:00 UTC
  - Booking 2: Redeemed 2025-09-13 06:21:42 UTC
  - Booking 3: Redeemed 2025-09-13 06:22:49 UTC

**Per-Redemption Supplier Payable**:
- `base_price_amount`: 127,500 IDR (supplier cost per redemption)
- `commission_amount`: 22,500 IDR (Tiket commission)
- `net_commission_amount`: 20,025 IDR (net after tax)
- `tiket_passes_subsidy_amount`: 12,000 IDR (Tiket subsidy per pass)

---

## Architectural Challenge

### Current Limitation

The system uses **`(order_id, order_detail_id, supplier_reference_id)`** to scope supplier timeline versions. This assumes:
- One supplier booking per order_detail
- Supplier payables generated at booking confirmation time

**Passes breaks this assumption** because:
- Multiple supplier payables need to be tracked under the same `(order_id, order_detail_id)`
- Each redemption event triggers a NEW payable (not a version update)
- `supplier_reference_id` (booking code) is the same for all passes in the package

### Current Query Logic (database.py:613-621)

```sql
ROW_NUMBER() OVER (
    PARTITION BY order_id, order_detail_id, supplier_reference_id
    ORDER BY supplier_timeline_version DESC
) as rn
```

**Problem**: This assumes one "latest" status per booking. For passes:
- We need to track **multiple concurrent payables** (one per redemption)
- Each redemption is NOT a version update; it's a **separate payable instance**

---

## Proposed Solution: Fulfillment Instance Tracking

### Add `fulfillment_instance_id` to Schema

Extend the composite key to support multi-instance payables within a single order_detail.

**Cross-Vertical Applicability**: While initially designed for Passes (redemption-triggered payables), this pattern supports any vertical with fulfillment-based payables:
- **Passes/Entertainment**: Per-redemption payables (e.g., playground visits)
- **Train/Bus**: Multi-ride passes with per-journey payables (potential future use case)
- **Airport Transfer**: Multi-leg trips with per-leg payables (potential future use case)
- **Tours**: Multi-day packages with per-day payables (potential future use case)

#### Schema Changes

**1. Add `fulfillment_instance_id` to `supplier_timeline`**

```sql
ALTER TABLE supplier_timeline ADD COLUMN fulfillment_instance_id TEXT;

-- New composite index
CREATE INDEX idx_supplier_redemption_instance
ON supplier_timeline(order_id, order_detail_id, supplier_reference_id, fulfillment_instance_id, supplier_timeline_version DESC);
```

**2. Add `fulfillment_instance_id` to `supplier_payable_lines`**

```sql
ALTER TABLE supplier_payable_lines ADD COLUMN fulfillment_instance_id TEXT;

-- New composite index
CREATE INDEX idx_payable_lines_redemption
ON supplier_payable_lines(order_id, order_detail_id, supplier_reference_id, fulfillment_instance_id, party_id, obligation_type);
```

#### Semantic Meaning

- **`NULL` (default)**: Traditional single-booking model (Flight, Hotel, Train, Car)
  - Supplier payable triggered at booking confirmation
  - One payable per order_detail
- **Non-NULL (e.g., `"ticket_code_1757809185001"`)**: Multi-instance fulfillment model
  - Supplier payables triggered by service delivery/consumption events
  - Multiple payables per order_detail, each scoped to a fulfillment instance

**Event Schema Note**: Verticals emit domain-specific field names in their events:
- Entertainment-service uses: `supplier.fulfillment_instance_id = "ticket_code_1757809185001"` (for passes)
- Future verticals can use the same field name with their own identifier format (e.g., `"journey_id_12345"`, `"leg_outbound"`)

**Scope Hierarchy**:
```
order_id → order_detail_id → supplier_reference_id → fulfillment_instance_id → supplier_timeline_version
```

---

### Event Schema Design

#### Event 1: Initial Booking Confirmation (No Redemption Yet)

```json
{
  "event_id": "evt_passes_booking_001",
  "event_type": "SupplierLifecycleEvent",
  "schema_version": "supplier.timeline.v2",
  "order_id": "1322884534",
  "order_detail_id": "1359185528",
  "emitted_at": "2025-09-13T06:19:45Z",
  "emitter_service": "entertainment-service",
  "idempotency_key": "entertainment_1359185528_confirmed_v1",

  "supplier": {
    "status": "Confirmed",
    "supplier_id": "PLAYGROUND_PARTNER_XYZ",
    "booking_code": "PKG-68c50c5284a6bf6699346e09",
    "supplier_ref": "PKG-68c50c5284a6bf6699346e09",
    "amount_due": 0,  // No payable until redemption
    "amount_basis": "redemption-triggered",
    "currency": "IDR",
    "fx_context": {
      "timestamp_fx_rate": "2025-09-13T06:19:45Z",
      "payment_currency": "IDR",
      "supply_currency": "IDR",
      "record_currency": "IDR",
      "gbv_currency": "IDR",
      "payment_value": 0,
      "supply_to_payment_fx_rate": 1.0,
      "supply_to_record_fx_rate": 1.0,
      "payment_to_gbv_fx_rate": 1.0,
      "source": "Treasury"
    },
    "entity_context": {
      "entity_code": "TNPL"
    }
  },
  "parties": [],  // No parties until redemption
  "meta": {
    "booking_type": "PASSES_RESERVATION",
    "total_passes_quantity": 3,
    "passes_validity_start": "2025-09-12T16:59:59Z",
    "passes_validity_end": "2025-09-28T16:59:59Z",
    "redemption_model": "on-demand"
  }
}
```

**Normalization Output**:
- `supplier_timeline_version`: 1
- `fulfillment_instance_id`: NULL (booking-level event)
- `status`: "Confirmed"
- `amount`: 0 (no payable yet)

---

#### Event 2: First Pass Redemption

```json
{
  "event_id": "evt_passes_redemption_001",
  "event_type": "SupplierLifecycleEvent",
  "schema_version": "supplier.timeline.v2",
  "order_id": "1322884534",
  "order_detail_id": "1359185528",
  "emitted_at": "2025-09-13T06:20:00.339Z",
  "emitter_service": "entertainment-service",
  "idempotency_key": "entertainment_1757809185001_redeemed_v1",

  "supplier": {
    "status": "ISSUED",
    "supplier_id": "PLAYGROUND_PARTNER_XYZ",
    "booking_code": "PKG-68c50c5284a6bf6699346e09",
    "supplier_ref": "PKG-68c50c5284a6bf6699346e09",
    "fulfillment_instance_id": "ticket_code_1757809185001",  // NEW: Unique redemption identifier
    "amount_due": 127500,  // Supplier cost per redemption
    "amount_basis": "net",
    "currency": "IDR",
    "fx_context": { /* same as booking */ },
    "entity_context": { "entity_code": "TNPL" }
  },
  "parties": [
    {
      "party_type": "SUPPLIER",
      "party_id": "PLAYGROUND_PARTNER_XYZ",
      "party_name": "Playground Partner XYZ",
      "lines": [
        {
          "obligation_type": "SUPPLIER",
          "amount": 127500,
          "amount_effect": "INCREASES_PAYABLE",
          "currency": "IDR",
          "description": "Supplier cost for pass redemption (ticket_code_1757809185001)"
        }
      ]
    },
    {
      "party_type": "INTERNAL",
      "party_id": "TNPL",
      "party_name": "PT Tiket Nusantara Persada Line",
      "lines": [
        {
          "obligation_type": "PLATFORM_SUBSIDY",
          "amount": 12000,
          "amount_effect": "INCREASES_COST",  // Internal cost, not payable to supplier
          "currency": "IDR",
          "calculation": {
            "basis": "per_redemption_subsidy",
            "rate": null
          },
          "description": "Tiket passes subsidy for redemption"
        }
      ]
    }
  ],
  "meta": {
    "redemption_timestamp": "2025-09-13T06:20:00.339Z",
    "redeemer_email_address": "[ENCRYPTED]",
    "ticket_code": "1757809185001",
    "price_tier_category": "CHILD",
    "customer_price_amount": 150000,
    "base_price_amount": 127500,
    "commission_amount": 22500
  }
}
```

**Normalization Output**:
- `supplier_timeline_version`: 2 (increments because same `order_detail_id`)
- **`fulfillment_instance_id`: `"ticket_code_1757809185001"`** ← NEW FIELD
- `status`: "ISSUED"
- `amount`: 127,500 IDR

**Payable Lines Inserted**:
```sql
INSERT INTO supplier_payable_lines VALUES (
  'evt_passes_redemption_001_SUPPLIER',     -- line_id
  'evt_passes_redemption_001',              -- event_id
  '1322884534',                             -- order_id
  '1359185528',                             -- order_detail_id
  'PKG-68c50c5284a6bf6699346e09',          -- supplier_reference_id
  'ticket_code_1757809185001',              -- fulfillment_instance_id (NEW)
  2,                                         -- supplier_timeline_version
  'SUPPLIER',                                -- obligation_type
  'SUPPLIER',                                -- party_type
  'PLAYGROUND_PARTNER_XYZ',                 -- party_id
  'Playground Partner XYZ',                 -- party_name
  127500,                                    -- amount
  'INCREASES_PAYABLE',                       -- amount_effect
  'IDR',                                     -- currency
  ...
);
```

---

#### Event 3: Second Pass Redemption (Same Day)

```json
{
  "event_id": "evt_passes_redemption_002",
  "event_type": "SupplierLifecycleEvent",
  "schema_version": "supplier.timeline.v2",
  "order_id": "1322884534",
  "order_detail_id": "1359185528",
  "emitted_at": "2025-09-13T06:21:42.612Z",
  "emitter_service": "entertainment-service",
  "idempotency_key": "entertainment_1757809307001_redeemed_v1",

  "supplier": {
    "status": "ISSUED",
    "supplier_id": "PLAYGROUND_PARTNER_XYZ",
    "booking_code": "PKG-68c50c5284a6bf6699346e09",
    "supplier_ref": "PKG-68c50c5284a6bf6699346e09",
    "fulfillment_instance_id": "ticket_code_1757809307001",  // Different ticket code
    "amount_due": 127500,
    "amount_basis": "net",
    "currency": "IDR",
    "fx_context": { /* same */ },
    "entity_context": { "entity_code": "TNPL" }
  },
  "parties": [
    {
      "party_type": "SUPPLIER",
      "party_id": "PLAYGROUND_PARTNER_XYZ",
      "party_name": "Playground Partner XYZ",
      "lines": [
        {
          "obligation_type": "SUPPLIER",
          "amount": 127500,
          "amount_effect": "INCREASES_PAYABLE",
          "currency": "IDR",
          "description": "Supplier cost for pass redemption (ticket_code_1757809307001)"
        }
      ]
    },
    {
      "party_type": "INTERNAL",
      "party_id": "TNPL",
      "party_name": "PT Tiket Nusantara Persada Line",
      "lines": [
        {
          "obligation_type": "PLATFORM_SUBSIDY",
          "amount": 12000,
          "amount_effect": "INCREASES_COST",
          "currency": "IDR",
          "description": "Tiket passes subsidy for redemption"
        }
      ]
    }
  ],
  "meta": {
    "redemption_timestamp": "2025-09-13T06:21:42.612Z",
    "ticket_code": "1757809307001",
    "price_tier_category": "CHILD"
  }
}
```

**Normalization Output**:
- `supplier_timeline_version`: 3 (increments)
- **`fulfillment_instance_id`: `"ticket_code_1757809307001"`** ← Different instance
- `status`: "ISSUED"
- `amount`: 127,500 IDR

---

### Query Logic Changes

#### Before (Current - Single Instance per Booking)

```sql
WITH latest_status AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, order_detail_id, supplier_reference_id
            ORDER BY supplier_timeline_version DESC
        ) as rn
    FROM supplier_timeline
    WHERE order_id = ?
)
SELECT * FROM latest_status WHERE rn = 1
```

**Problem**: Returns only ONE row per booking (latest version). For passes with 3 redemptions, this loses 2 payables.

---

#### After (Multi-Instance Support)

```sql
WITH latest_status AS (
    SELECT *,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, order_detail_id, supplier_reference_id,
                         COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__')
            ORDER BY supplier_timeline_version DESC
        ) as rn
    FROM supplier_timeline
    WHERE order_id = ?
)
SELECT * FROM latest_status WHERE rn = 1
```

**Key Change**:
- `PARTITION BY` now includes `COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__')`
- Returns **multiple rows** per booking (one per redemption instance)
- Backward compatible: NULL fulfillment_instance_id treated as single-instance

**Result for Passes Example**:
```
order_detail_id | supplier_ref | fulfillment_instance_id        | version | status | amount
1359185528      | PKG-68c...   | NULL                          | 1       | Confirmed | 0
1359185528      | PKG-68c...   | ticket_code_1757809185001    | 2       | ISSUED | 127500
1359185528      | PKG-68c...   | ticket_code_1757809307001    | 3       | ISSUED | 127500
1359185528      | PKG-68c...   | ticket_code_1757772769001    | 4       | ISSUED | 127500
```

---

### Updated `get_total_effective_payables` Query

```sql
-- Step 1: Get latest status per (order_detail_id, supplier_reference_id, fulfillment_instance_id)
WITH latest_status AS (
    SELECT
        order_id,
        order_detail_id,
        supplier_id,
        supplier_reference_id,
        fulfillment_instance_id,  -- NEW
        status,
        amount,
        amount_basis,
        cancellation_fee_amount,
        currency,
        supplier_timeline_version,
        ROW_NUMBER() OVER (
            PARTITION BY order_id, order_detail_id, supplier_reference_id,
                         COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__')  -- NEW
            ORDER BY supplier_timeline_version DESC
        ) as rn
    FROM supplier_timeline
    WHERE order_id = ?
)
SELECT * FROM latest_status WHERE rn = 1;

-- Step 2: For each instance, get party-level projection (scoped to fulfillment_instance_id)
WITH latest_per_party AS (
    SELECT party_id, obligation_type, MAX(supplier_timeline_version) as latest_version
    FROM supplier_payable_lines
    WHERE order_id = ? AND order_detail_id = ?
      AND supplier_reference_id = ?
      AND COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__') = ?  -- NEW
      AND supplier_timeline_version >= 1
    GROUP BY party_id, obligation_type
)
SELECT p.obligation_type, p.party_type, p.party_id, p.party_name, p.amount, p.amount_effect, p.currency
FROM supplier_payable_lines p
JOIN latest_per_party l
  ON p.party_id = l.party_id
  AND p.obligation_type = l.obligation_type
  AND p.supplier_timeline_version = l.latest_version
WHERE p.order_id = ? AND p.order_detail_id = ?
  AND p.supplier_reference_id = ?
  AND COALESCE(p.fulfillment_instance_id, '__BOOKING_LEVEL__') = ?;  -- NEW
```

---

## UI/UX Display Changes

### Order Explorer: Supplier Payables Section

**Before (Single Supplier per Order Detail)**:
```
### Order Detail: 1359185528
Status: 🟢 ISSUED | Supplier: PLAYGROUND_PARTNER_XYZ
Total Payable: 127,500 IDR
```

**After (Multi-Instance Support)**:
```
### Order Detail: 1359185528
Booking: PKG-68c50c5284a6bf6699346e09 | Supplier: PLAYGROUND_PARTNER_XYZ

📦 Booking Confirmation (2025-09-13 06:19:45)
   Status: 🟢 Confirmed | Amount: 0 IDR (redemption-triggered)

🎟️ Redemption Instance: ticket_code_1757809185001
   Redeemed: 2025-09-13 06:20:00 UTC
   Status: 🟢 ISSUED | Supplier Payable: 127,500 IDR
   ├─ SUPPLIER: 127,500 IDR (PLAYGROUND_PARTNER_XYZ)
   └─ PLATFORM_SUBSIDY: 12,000 IDR (TNPL - Internal Cost)

🎟️ Redemption Instance: ticket_code_1757809307001
   Redeemed: 2025-09-13 06:21:42 UTC
   Status: 🟢 ISSUED | Supplier Payable: 127,500 IDR
   ├─ SUPPLIER: 127,500 IDR (PLAYGROUND_PARTNER_XYZ)
   └─ PLATFORM_SUBSIDY: 12,000 IDR (TNPL - Internal Cost)

🎟️ Redemption Instance: ticket_code_1757772769001
   Redeemed: 2025-09-13 06:22:49 UTC
   Status: 🟢 ISSUED | Supplier Payable: 127,500 IDR
   ├─ SUPPLIER: 127,500 IDR (PLAYGROUND_PARTNER_XYZ)
   └─ PLATFORM_SUBSIDY: 12,000 IDR (TNPL - Internal Cost)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Total Supplier Payable (All Redemptions): 382,500 IDR
Total Platform Subsidy: 36,000 IDR
```

---

## Migration Strategy

### Phase 1: Schema Extension (Non-Breaking)

1. **Add nullable `fulfillment_instance_id` column** to both tables
2. **Add composite indexes** for new query patterns
3. **Update ingestion pipeline** to support new field (default NULL for non-passes)
4. **Backward compatibility**: All existing data has NULL fulfillment_instance_id (treated as single-instance)

```python
# pipeline.py - ingestion logic
def _ingest_supplier_lifecycle(self, event_data: Dict[str, Any]):
    event = SupplierLifecycleEvent(**event_data)

    # NEW: Extract fulfillment_instance_id (optional)
    fulfillment_instance_id = None
    if event.supplier and hasattr(event.supplier, 'fulfillment_instance_id'):
        fulfillment_instance_id = event.supplier.fulfillment_instance_id

    # Version scoping now considers fulfillment_instance_id
    latest_supplier_version = self.db.get_latest_supplier_timeline_version(
        event.order_id,
        event.order_detail_id,
        fulfillment_instance_id  # NEW parameter
    )
    supplier_timeline_version = (latest_supplier_version or 0) + 1

    normalized = NormalizedSupplierTimeline(
        # ... existing fields ...
        fulfillment_instance_id=fulfillment_instance_id,  # NEW
        supplier_timeline_version=supplier_timeline_version
    )
```

### Phase 2: Passes Service Integration

1. **Passes service emits events** with `fulfillment_instance_id`
2. **Initial booking event**: `fulfillment_instance_id = NULL`, `amount_due = 0`
3. **Per-redemption events**: `fulfillment_instance_id = ticket_code`, `amount_due = base_price`

### Phase 3: Query Updates

1. **Update `get_total_effective_payables`** to use new partitioning logic
2. **Update UI components** to display multi-instance payables
3. **Add aggregation views** for total payables per booking (sum across instances)

---

## Alternative: Option B - Use `meta` JSON Field (Not Recommended)

**Approach**: Store `fulfillment_instance_id` in `meta` JSON column instead of dedicated field.

**Pros**:
- No schema migration needed
- Flexible for other metadata

**Cons**:
- ❌ Cannot index on JSON field efficiently in SQLite
- ❌ Complex query logic with JSON extraction
- ❌ Poor query performance for production scale (Spanner supports JSON indexing but adds complexity)
- ❌ Violates "make composite key explicit" principle

**Verdict**: Not recommended. Use dedicated column (Option A).

---

## Edge Cases & Considerations

### 1. Partial Redemption Refunds

**Scenario**: Customer redeems 2 of 3 passes, then requests refund for the 3rd unredeemed pass.

**Solution**:
- Customer pricing uses `RefundIssued` event with negative components (existing pattern)
- Supplier payable: NO new supplier event (unredeemed = no payable generated yet)
- If already redeemed and refunded: Emit `SupplierLifecycleEvent` with `status: "CancelledWithFee"` and `fulfillment_instance_id` matching the refunded ticket

```json
{
  "event_type": "SupplierLifecycleEvent",
  "supplier": {
    "status": "CancelledWithFee",
    "fulfillment_instance_id": "ticket_code_1757809185001",
    "amount_due": 0,
    "cancellation_fee_amount": 0
  },
  "parties": []  // Empty parties = exclude timeline obligations for this instance
}
```

### 2. Bulk Redemption (All at Once)

**Scenario**: Customer uses all 3 passes in a single visit (e.g., family with 3 kids).

**Solution**: Emit **3 separate events** with different `fulfillment_instance_id` values (one per ticket code).

**Rationale**: Maintains lineage clarity for Finance reconciliation (each payable traceable to specific ticket).

### 3. Expired Unredeemed Passes

**Scenario**: Customer purchases 3 passes but only uses 2 before expiry date.

**Solution**:
- No supplier payable generated for unredeemed passes (no event emitted)
- Customer pricing already recorded at purchase (full payment upfront)
- Finance treatment: Unredeemed passes become **breakage revenue** (customer paid, supplier not owed)

### 4. Same-Day Multiple Redemptions (Deduplication Risk)

**Scenario**: All 3 passes redeemed within minutes (as seen in sample data).

**Protection**:
- `idempotency_key` includes `ticket_code`: `"entertainment_{ticket_code}_redeemed_v1"`
- Event bus deduplication ensures no double-processing
- Each redemption has unique `event_id` and `fulfillment_instance_id`

---

## Production Readiness Checklist

### Schema Migration
- [ ] Add `fulfillment_instance_id TEXT` to `supplier_timeline` (nullable)
- [ ] Add `fulfillment_instance_id TEXT` to `supplier_payable_lines` (nullable)
- [ ] Create composite indexes with `COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__')`
- [ ] Backfill NULL for existing data (default behavior, no action needed)

### Ingestion Pipeline
- [ ] Update `_ingest_supplier_lifecycle` to extract `fulfillment_instance_id`
- [ ] Update `get_latest_supplier_timeline_version` to accept `fulfillment_instance_id` parameter
- [ ] Add validation: If `fulfillment_instance_id` present, require `status IN ('ISSUED', 'CancelledWithFee', 'CancelledNoFee')`
- [ ] Update Pydantic models to include optional `fulfillment_instance_id` field

### Query Logic
- [ ] Update `get_total_effective_payables` to partition by `fulfillment_instance_id`
- [ ] Update party-level projection queries to scope by `fulfillment_instance_id`
- [ ] Add aggregation helper: `get_total_payables_by_booking` (sum across all instances)

### UI Components
- [ ] Update Order Explorer to display multi-instance payables
- [ ] Add collapsible sections for redemption instances
- [ ] Show booking-level summary + per-instance breakdown
- [ ] Add "Redemption Timeline" visualization (timeline chart with redemption events)

### Testing
- [ ] Integration test: 3-pass redemption scenario (sample data)
- [ ] Edge case test: Partial refund (1 of 3 passes)
- [ ] Edge case test: Expired unredeemed passes (no supplier event)
- [ ] Performance test: 50-pass package (stress test pagination)

### Documentation
- [ ] Update PRD with redemption-triggered payable model
- [ ] Add Passes vertical to event catalog
- [ ] Document `fulfillment_instance_id` in EVENT_FIELD_REFERENCE.md
- [ ] Add Passes example to end_to_end_evolution.html

---

## Summary

### Key Design Decision

**Add `fulfillment_instance_id` as a dedicated schema field** to support:
- Multi-instance payables within a single order_detail
- Clear lineage for redemption-triggered supplier costs
- Scalable query performance with proper indexing

### Composite Key Evolution

**Before (Single Instance)**:
```
(order_id, order_detail_id, supplier_reference_id)
```

**After (Multi-Instance)**:
```
(order_id, order_detail_id, supplier_reference_id, fulfillment_instance_id)
```

### Backward Compatibility

- All existing data: `fulfillment_instance_id = NULL` (single-instance model)
- Query logic: Use `COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__')` for partitioning
- No breaking changes to existing verticals (Flight, Hotel, Train, Car, Ferry, Bus)

### Event Lifecycle for Passes

1. **Booking Confirmed**: `status: "Confirmed"`, `fulfillment_instance_id: NULL`, `amount_due: 0`
2. **First Redemption**: `status: "ISSUED"`, `fulfillment_instance_id: "ticket_code_XXX"`, `amount_due: 127500`
3. **Second Redemption**: `status: "ISSUED"`, `fulfillment_instance_id: "ticket_code_YYY"`, `amount_due: 127500`
4. **Third Redemption**: `status: "ISSUED"`, `fulfillment_instance_id: "ticket_code_ZZZ"`, `amount_due: 127500`
5. **Optional Refund**: `status: "CancelledWithFee"`, `fulfillment_instance_id: "ticket_code_YYY"`, `parties: []`

---

## Next Steps

1. **Review with Passes/Entertainment team**: Validate redemption event schema
2. **Schema migration PR**: Add `fulfillment_instance_id` column to staging environment
3. **Prototype integration**: Add sample Passes events to prototype for validation
4. **Production rollout**: Phased deployment (Passes only → gradual vertical expansion if needed)
