# Multi-Party Supplier Lifecycle Implementation Plan

## Overview

This document tracks the implementation of the multi-party supplier lifecycle event structure with projection-based effective payables calculation.

**Goal:** Enable explicit multi-party obligations (supplier, affiliate, tax) with `amount_effect` directionality while supporting projection-based carry-forward for unchanged obligations on cancellation.

**Key Design Decisions:**
- **Option B (Projection)**: Cancellation events can omit `parties` array if obligations unchanged; party-level projection carries forward v1 obligations
- **Status-Driven Baseline**: Supplier timeline status determines baseline payable (amount_due vs cancellation_fee)
- **Standalone Adjustments**: Partner penalties/credits use version = -1 to persist regardless of supplier status

---

## Implementation Status

### ✅ Phase 1: COMPLETED - Update Event Models with Multi-Party Structure

**File:** `src/models/events.py`

**Changes Implemented:**

1. **Added 3 New Enums:**
```python
class AmountEffect(str, Enum):
    INCREASES_PAYABLE = "INCREASES_PAYABLE"  # Positive obligation (we owe more)
    DECREASES_PAYABLE = "DECREASES_PAYABLE"  # Negative obligation (we owe less)

class AmountBasis(str, Enum):
    GROSS = "gross"  # Before commissions/deductions
    NET = "net"      # After commissions/deductions

class ObligationType(str, Enum):
    SUPPLIER_BASELINE = "SUPPLIER_BASELINE"
    SUPPLIER_COMMISSION_RETENTION = "SUPPLIER_COMMISSION_RETENTION"
    AFFILIATE_COMMISSION = "AFFILIATE_COMMISSION"
    TAX_VAT_ON_AFFILIATE_COMMISSION = "TAX_VAT_ON_AFFILIATE_COMMISSION"
    AFFILIATE_PENALTY = "AFFILIATE_PENALTY"
    SUPPLIER_CANCELLATION_FEE = "SUPPLIER_CANCELLATION_FEE"
```

2. **Added PayableLine Model:**
```python
class PayableLine(BaseModel):
    obligation_type: Union[ObligationType, str]
    amount: Union[int, float]
    currency: str
    amount_effect: Union[AmountEffect, str]  # NEW
    calculation: Optional[Dict[str, Any]] = None
    description: Optional[str] = None
```

3. **Added Party Model:**
```python
class Party(BaseModel):
    party_type: str  # "SUPPLIER", "AFFILIATE", "TAX_AUTHORITY"
    party_id: str
    party_name: str
    lines: List[PayableLine]
```

4. **Updated Cancellation Model:**
```python
class Cancellation(BaseModel):
    fee_amount: Optional[int] = None
    fee_currency: Optional[str] = None
    replaces_original_cost: bool = False  # NEW
```

5. **Updated Supplier Model:**
```python
class Supplier(BaseModel):
    # ... existing fields ...
    amount_basis: Optional[Union[AmountBasis, str]] = None  # NEW
    affiliate: Optional[Affiliate] = None  # DEPRECATED: Use parties array
    supplier_commission: Optional[SupplierCommission] = None  # DEPRECATED
```

6. **Updated SupplierLifecycleEvent:**
```python
class SupplierLifecycleEvent(BaseModel):
    schema_version: str = "supplier.timeline.v2"  # Version bump
    supplier: Supplier
    parties: Optional[List[Party]] = None  # NEW: Multi-party payables
```

7. **Added PartnerAdjustmentEvent:**
```python
class PartnerAdjustmentEvent(BaseModel):
    event_type: str = "PartnerAdjustmentEvent"
    schema_version: str = "partner.adjustment.v1"
    order_id: str
    order_detail_id: str
    party: Dict[str, str]
    line: PayableLine  # Single line (version = -1)
```

---

### ✅ Phase 2: COMPLETED - Update Database Schema for Amount Effect and Basis

**File:** `src/storage/database.py`

**Changes Implemented:**

1. **Updated `supplier_timeline` Table:**
```sql
CREATE TABLE IF NOT EXISTS supplier_timeline (
    -- ... existing fields ...
    amount INTEGER,
    amount_basis TEXT,  -- NEW: "gross" or "net"
    currency TEXT,
    -- ... existing fields ...
    fx_context TEXT,  -- NEW: JSON for FX rates
    entity_context TEXT,  -- NEW: JSON for entity context
    -- ... existing fields ...
)
```

2. **Updated `supplier_payable_lines` Table:**
```sql
CREATE TABLE IF NOT EXISTS supplier_payable_lines (
    -- ... existing fields ...
    amount INTEGER NOT NULL,
    amount_effect TEXT NOT NULL DEFAULT 'INCREASES_PAYABLE',  -- NEW
    currency TEXT NOT NULL,
    -- ... existing fields ...
)
```

**Migration Note:** Schema uses `CREATE TABLE IF NOT EXISTS`, so new columns are added automatically on next database initialization. For existing databases, manual migration would be needed.

---

### 📋 Phase 3: PENDING - Update Ingestion Pipeline to Handle New Event Structure

**Files to Modify:**
- `src/ingestion/pipeline.py`
- `src/storage/database.py` (insert methods)

**Tasks:**

1. **Add Event Router in `pipeline.py`:**
```python
def process_event(self, event_data: dict):
    event_type = event_data.get('event_type')
    schema_version = event_data.get('schema_version', '')

    if event_type == 'SupplierLifecycleEvent' and 'v2' in schema_version:
        return self.process_supplier_lifecycle_v2(event_data)
    elif event_type == 'PartnerAdjustmentEvent':
        return self.process_partner_adjustment(event_data)
    # ... existing handlers
```

2. **Implement `process_supplier_lifecycle_v2()`:**
   - Validate event with Pydantic
   - Assign `supplier_timeline_version` (monotonic increment)
   - Insert supplier timeline record with `amount_basis`
   - Extract parties array → insert payable lines with `amount_effect`
   - Link payable lines to timeline version

3. **Implement `process_partner_adjustment()`:**
   - Validate PartnerAdjustmentEvent
   - Insert payable line with `supplier_timeline_version = -1`
   - Include `amount_effect` from event

4. **Update Database Insert Methods:**
```python
def insert_supplier_timeline(self, ..., amount_basis, fx_context, entity_context):
    # Updated INSERT with new columns

def insert_supplier_payable_line(self, ..., amount_effect, ...):
    # Updated INSERT with amount_effect
```

---

### 📋 Phase 4: PENDING - Update Effective Payables Calculation with Party-Level Projection

**File:** `src/storage/database.py`

**Task:** Update `get_total_effective_payables()` method to use party-level projection

**New Query Logic:**
```sql
-- When include_timeline_obligations = True:
WITH latest_per_party AS (
    SELECT
        party_id,
        obligation_type,
        MAX(supplier_timeline_version) as latest_version
    FROM supplier_payable_lines
    WHERE order_id = ? AND order_detail_id = ?
    GROUP BY party_id, obligation_type
)
SELECT
    p.obligation_type,
    p.party_id,
    p.party_name,
    p.amount,
    p.amount_effect,
    p.currency
FROM supplier_payable_lines p
JOIN latest_per_party l
  ON p.party_id = l.party_id
  AND p.obligation_type = l.obligation_type
  AND p.supplier_timeline_version = l.latest_version
WHERE p.order_id = ? AND p.order_detail_id = ?
```

**Apply `amount_effect`:**
```python
total_adjustment = 0
for obl in obligations:
    if obl['amount_effect'] == 'INCREASES_PAYABLE':
        total_adjustment += obl['amount']
    elif obl['amount_effect'] == 'DECREASES_PAYABLE':
        total_adjustment -= obl['amount']
```

---

### 📋 Phase 5: PENDING - Create Sample Events for All Scenarios

**Directory:** `components-helper/supplier_lifecycle_v2/`

**Files to Create:**

1. **`1_issued_with_parties.json`** - ISSUED status with full multi-party breakdown
2. **`2_cancelled_with_fee_no_parties.json`** - CancelledWithFee with empty parties (projection carries forward)
3. **`3_cancelled_with_adjusted_affiliate.json`** - CancelledWithFee with updated affiliate commission
4. **`components-helper/partner_adjustment/1_affiliate_penalty.json`** - Standalone penalty (version = -1)

---

### 📋 Phase 6: PENDING - Update Producer Playground with New Event Emitters

**File:** `src/ui/producer_playground.py`

**Tasks:**
- Add tab for "Supplier Lifecycle v2"
- Add tab for "Partner Adjustment"
- Form controls for parties array builder
- amount_effect radio button selector
- Sample event templates with pre-filled data

---

### 📋 Phase 7: PENDING - Update UI to Display Amount Effect and Party-Level Projections

**Files:**
- `src/ui/order_explorer.py` - Add color coding for amount_effect
- `src/ui/raw_storage_viewer.py` - Add amount_basis and amount_effect columns

**Color Coding:**
- INCREASES_PAYABLE → Red/Pink
- DECREASES_PAYABLE → Green

---

### 📋 Phase 8: PENDING - Test End-to-End Flow with All Scenarios

**Test Scenarios:**

1. **Scenario A: Issued → Effective Payables Includes All Parties**
   - Emit `1_issued_with_parties.json`
   - Verify supplier_timeline.amount_basis = "gross"
   - Verify 3 payable lines created (supplier retention, affiliate commission, tax)
   - Verify effective payables = 300000 - 45000 + 4694 + 516 = 260,210 IDR

2. **Scenario B: Issued → Cancelled → Affiliate Obligations Carried Forward**
   - Emit `1_issued_with_parties.json` (v1)
   - Emit `2_cancelled_with_fee_no_parties.json` (v2)
   - Verify v2 has empty parties array
   - Verify effective payables query uses party-level projection
   - Expected: baseline = 50,000 (cancellation fee), affiliates carried from v1

3. **Scenario C: Issued → Cancelled → Partner Penalty Persists**
   - Emit `1_issued_with_parties.json` (v1)
   - Emit `2_cancelled_with_fee_no_parties.json` (v2)
   - Emit `1_affiliate_penalty.json` (standalone, version = -1)
   - Verify penalty appears in effective payables even with CancelledWithFee status

4. **Scenario D: Issued → Cancelled with Adjusted Affiliate**
   - Emit `1_issued_with_parties.json` (v1)
   - Emit `3_cancelled_with_adjusted_affiliate.json` (v2 with updated affiliate lines)
   - Verify v2 affiliate commission = 2347 (50% of original)
   - Verify party-level projection returns v2 affiliate (latest wins)

---

## Key Event Examples

### SupplierLifecycleEvent v2 (ISSUED)
```json
{
  "event_type": "SupplierLifecycleEvent",
  "schema_version": "supplier.timeline.v2",
  "order_id": "ORD-2001",
  "order_detail_id": "OD-2001",
  "supplier": {
    "status": "ISSUED",
    "supplier_id": "NATIVE",
    "amount_due": 300000,
    "amount_basis": "gross",
    "currency": "IDR"
  },
  "parties": [
    {
      "party_type": "SUPPLIER",
      "party_id": "NATIVE",
      "lines": [{
        "obligation_type": "SUPPLIER_COMMISSION_RETENTION",
        "amount": 45000,
        "amount_effect": "DECREASES_PAYABLE",
        "currency": "IDR"
      }]
    },
    {
      "party_type": "AFFILIATE",
      "party_id": "100005361",
      "lines": [
        {
          "obligation_type": "AFFILIATE_COMMISSION",
          "amount": 4694,
          "amount_effect": "INCREASES_PAYABLE",
          "currency": "IDR"
        },
        {
          "obligation_type": "TAX_VAT_ON_AFFILIATE_COMMISSION",
          "amount": 516,
          "amount_effect": "INCREASES_PAYABLE",
          "currency": "IDR"
        }
      ]
    }
  ]
}
```

### SupplierLifecycleEvent v2 (CancelledWithFee, Empty Parties)
```json
{
  "event_type": "SupplierLifecycleEvent",
  "schema_version": "supplier.timeline.v2",
  "order_id": "ORD-2001",
  "order_detail_id": "OD-2001",
  "supplier": {
    "status": "CancelledWithFee",
    "supplier_id": "NATIVE",
    "amount_due": 50000,
    "amount_basis": "net",
    "currency": "IDR",
    "cancellation": {
      "fee_amount": 50000,
      "replaces_original_cost": true
    }
  },
  "parties": []  // Empty: projection carries forward v1 affiliate obligations
}
```

### PartnerAdjustmentEvent (Standalone Penalty)
```json
{
  "event_type": "PartnerAdjustmentEvent",
  "schema_version": "partner.adjustment.v1",
  "order_id": "ORD-2001",
  "order_detail_id": "OD-2001",
  "party": {
    "party_type": "AFFILIATE",
    "party_id": "100005361",
    "party_name": "Partner CFD"
  },
  "line": {
    "obligation_type": "AFFILIATE_PENALTY",
    "amount": 500000,
    "amount_effect": "INCREASES_PAYABLE",
    "currency": "IDR",
    "description": "Failed check-in compensation per SLA"
  }
}
```

---

## Database Schema Summary

### supplier_timeline
- `amount_basis` (TEXT): "gross" or "net"
- `fx_context` (TEXT): JSON FX rates
- `entity_context` (TEXT): JSON entity context

### supplier_payable_lines
- `amount_effect` (TEXT): "INCREASES_PAYABLE" or "DECREASES_PAYABLE"
- `supplier_timeline_version` (INTEGER): -1 for standalone adjustments, >= 1 for timeline-linked

---

## Next Steps

1. ✅ Phase 1: Event Models - **COMPLETED**
2. ✅ Phase 2: Database Schema - **COMPLETED**
3. ⏳ Phase 3: Ingestion Pipeline - **IN PROGRESS**
4. ⏳ Phase 4: Effective Payables Calculation
5. ⏳ Phase 5: Sample Events
6. ⏳ Phase 6: Producer Playground
7. ⏳ Phase 7: UI Updates
8. ⏳ Phase 8: End-to-End Testing

**Recommendation:** Continue with Phase 3 to implement event ingestion, then validate with Phase 5 sample events before proceeding to UI updates.
