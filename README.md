# Unified Pricing Read Layer (UPRL) Prototype

An interactive Streamlit prototype demonstrating the **Unified Pricing Read Layer** architecture for Tiket.com's Order Platform.

[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32+-red.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-Internal-yellow.svg)]()

## Overview

This prototype simulates the complete data flow from producer events through Order Core ingestion to normalized storage, showcasing:

- **Event-driven architecture** with standardized producer events
- **Multi-instance payables** for passes redemptions, multi-ride transport, tours
- **Party-level projection** with amount_effect directionality (INCREASES/DECREASES)
- **Dual ID strategy** (semantic + instance IDs) for stable component identity
- **Version families** for independent evolution of pricing, payment, supplier, and refund timelines
- **Append-only storage** with immutable audit trails
- **Component lineage tracking** through refunds and repricing
- **B2B affiliate tracking** with multi-party obligations

## 🆕 What's New in v2.0

### Multi-Instance Payables
Handle scenarios where 1 order + 1 order_detail generates multiple supplier payables over time:
- **Entertainment Passes**: Each ticket redemption generates separate payable
- **Multi-Ride Transport**: Train/bus multi-journey tickets with per-leg costs
- **Tours & Transfers**: Multiple tour instances or transfer legs
- **Recurring Services**: Each fulfillment event generates payable

**Technical Implementation**:
- New field: `fulfillment_instance_id` in supplier events and database
- Partition key: `(order_id, order_detail_id, supplier_ref, fulfillment_instance_id)`
- NULL-safe: `fulfillment_instance_id=NULL` = single-instance (backward compatible)
- UI Support: Multi-instance display in Order Explorer and Latest State Projection

### Party-Level Projection v2
Track obligations across multiple parties with directional effects:
- **Amount Effect**: `INCREASES_PAYABLE` (add) or `DECREASES_PAYABLE` (subtract)
- **Party Types**: SUPPLIER, AFFILIATE, TAX_AUTHORITY, INTERNAL
- **Obligation Types**: SUPPLIER_COST, COMMISSION, COMMISSION_VAT, CANCELLATION_FEE, etc.
- **Status-Driven Logic**: Different obligation inclusion rules per supplier status

## Features

### 🎮 Producer Playground
Emit sample events from various producers:

**Pricing Events**
- Hotel, Flight, Train, Entertainment bookings
- Repricing scenarios
- Refund component tracking

**Payment Events**
- Payment lifecycle (checkout → authorized → captured → refunded)
- Multiple payment methods (credit card, wallet, **loyalty points/TiketPoints**)
- Payment instrument tracking

**Supplier & Payable Events v2**
- Supplier lifecycle (Confirmed → ISSUED → Invoiced → Cancelled)
- **Multi-instance payables** (booking + multiple redemptions)
- **Party-level obligations** with amount_effect
- FX context and entity context

**Refund Events**
- Refund timeline (INITIATED → PROCESSING → ISSUED → CLOSED)
- Component-level refund tracking
- Lineage to original components

### ⚙️ Ingestion Console
- View Dead Letter Queue (DLQ) entries for failed events
- Monitor ingestion statistics (orders, components, events)
- Inspect validation errors and schema violations
- Track event processing throughput

### 🔍 Order Explorer
Comprehensive order analysis with 7 tabs:

1. **Latest Pricing**: Current pricing breakdown with component cards
2. **Version History**: All pricing versions with snapshot details
3. **Component Lineage**: Refund chains and repricing history
4. **Payment Timeline**: Payment lifecycle with instrument details
5. **Supplier Timeline**: Supplier status changes per order_detail
6. **Supplier Payables v2** 🆕: Multi-instance payables with party-level projection
   - Booking-level baseline (0 for redemption-triggered)
   - Per-redemption payables with ticket codes
   - Party-separated obligations (supplier, affiliate, tax, internal)
   - Amount effect visualization (increases vs decreases)
7. **Refund Timeline**: Refund status tracking

### 🗄️ Raw Data Storage
View raw table contents for debugging:
- pricing_components_fact (all columns visible)
- payment_timeline
- supplier_timeline
- supplier_payable_lines 🆕
- refund_timeline
- dlq (Dead Letter Queue)

Features: Pagination, filtering, column inspection

### 📊 Latest State Projection
Unified view of complete order state:
- Latest pricing breakdown
- Current payment status
- Supplier timeline per order_detail
- Refund summary
- **Supplier payables** (with multi-instance support) 🆕

One-page comprehensive view with real-time aggregation.

### 🧪 Stress Tests
Test edge cases and validate system behavior:
- Out-of-order event processing (v3 before v2)
- Duplicate event handling (idempotency)
- Invalid schema validation
- Missing required fields
- Negative amount validation
- Version gap detection

## Architecture

```
Producers (Vertical/Payment/Supplier/Refund)
       ↓ emit standardized events
Order Core Ingestion Pipeline
       ├─ Schema validation (Pydantic v2)
       ├─ Dual ID generation (semantic + instance)
       ├─ Version key assignment (per version family)
       ├─ Normalization (producer format → storage format)
       └─ Multi-instance handling (fulfillment_instance_id scoping)
          ↓
Unified Pricing Read Layer (SQLite)
       ├─ Hot Store (latest projections via views)
       │   - order_pricing_latest
       │   - payment_timeline_latest
       │   - supplier_timeline_latest
       │   - refund_timeline_latest
       │
       └─ Cold Store (append-only fact tables)
           - pricing_components_fact
           - payment_timeline
           - supplier_timeline
           - supplier_payable_lines 🆕
           - refund_timeline
           - dlq
```

## Installation

### Prerequisites
- Python 3.12 or higher
- pip package manager

### Setup

1. **Clone the repository** (if not already done):
```bash
cd /path/to/order-pm/order-pm-documentation/Unified-Pricing-Read-Layer/prototype
```

2. **Create virtual environment**:
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies**:
```bash
pip install -r requirements.txt
```

## Running the Prototype

Start the Streamlit app:

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

**Alternative**: Use the provided shell script:
```bash
./run.sh
```

## Running Tests

All tests are organized in the `tests/` directory:

```bash
# Activate virtual environment
source venv/bin/activate

# Run individual tests
python tests/test_b2b_real_files.py       # B2B affiliate integration test
python tests/test_rebooking_flow.py       # Status-driven obligations
python tests/test_refund_issued.py        # Refund lineage
python tests/test_payment_fee_scenario.py # Payment fees
python tests/test_b2b_affiliate.py        # Manual affiliate flow

# Debug multi-instance payables
python debug_multi_instance.py            # Test passes redemption scenario
```

See `tests/README.md` for detailed test documentation.

## Project Structure

```
prototype/
├── app.py                          # Main Streamlit application (navigation)
├── requirements.txt                # Python dependencies
├── run.sh                          # Launch script
├── debug_multi_instance.py         # 🆕 Debug tool for multi-instance payables
├── .gitignore                      # Git ignore rules
│
├── README.md                       # This file
├── CLAUDE.md                       # 🆕 Comprehensive AI guidance
│
├── src/
│   ├── models/
│   │   ├── events.py              # Producer event schemas (Pydantic v2)
│   │   │                           # 🆕 Updated: Supplier model has fulfillment_instance_id
│   │   └── normalized.py          # Normalized storage models
│   │
│   ├── ingestion/
│   │   ├── pipeline.py            # Order Core ingestion logic
│   │   │                           # 🆕 Updated: _ingest_supplier_lifecycle_v2()
│   │   └── id_generator.py        # Dual ID generation (semantic + instance)
│   │
│   ├── storage/
│   │   └── database.py            # SQLite schema and queries
│   │                               # 🆕 Updated: get_total_effective_payables()
│   │                               #            Multi-instance query logic
│   │
│   └── ui/
│       ├── producer_playground.py # Producer event emission UI
│       ├── order_explorer.py      # Order browsing and exploration UI
│       │                           # 🆕 Updated: render_supplier_payables()
│       ├── unified_order_view.py  # Latest state projection UI
│       ├── raw_storage_viewer.py  # Raw table viewer UI
│       ├── stress_tests.py        # Edge case testing UI
│       ├── json_editor.py         # JSON editing UI
│       └── json_loader.py         # File loading UI
│
├── sample_events/                  # Sample JSON events (organized)
│   ├── pricing_events/
│   │   └── hotel-3-night-simple.json
│   │
│   ├── payment_timeline/
│   │   ├── 010-checkout.json
│   │   ├── 020-authorized.json
│   │   ├── 030-captured.json
│   │   └── ttd-passes-prod-1322884534/
│   │       └── 001-captured.json  # 🆕 Loyalty/TiketPoints payment
│   │
│   ├── supplier_and_payable_event/
│   │   ├── supplier-lifecycle/
│   │   │   ├── 001-supplier-issued-multi-party-with-amount-effect.json
│   │   │   ├── 002-supplier-cancelled-projection-based.json
│   │   │   └── 003-supplier-cancelled-adjusted-affiliate.json
│   │   │
│   │   ├── ttd-passes-prod-1322884534/  # 🆕 Multi-instance example
│   │   │   ├── 001-booking-confirmed.json
│   │   │   ├── 002-redemption-1.json
│   │   │   ├── 003-redemption-2.json
│   │   │   └── 004-redemption-3.json
│   │   │
│   │   ├── b2b-affiliate/
│   │   ├── train-prod-1327314937/
│   │   ├── supplier-rebooking-case/
│   │   └── partner-adjustment-SF/
│   │
│   └── refund_timeline/
│       └── refund-lifecycle/
│           ├── 1_initiated.json
│           ├── 2_processing.json
│           ├── 3_issued.json
│           └── 4_closed.json
│
├── tests/                          # Test suite
│   ├── README.md                   # Test documentation
│   ├── test_b2b_real_files.py      # B2B affiliate integration
│   ├── test_rebooking_flow.py      # Status-driven obligations
│   ├── test_refund_issued.py       # Refund lineage
│   ├── test_payment_fee_scenario.py# Payment fees
│   ├── test_b2b_affiliate.py       # Manual affiliate flow
│   └── test_v2_scenarios.py        # v2 model scenarios
│
├── data/
│   └── uprl.db                     # SQLite database (gitignored, auto-created)
│
├── docs/                           # 🆕 Organized documentation
│   ├── ARCHITECTURE.md             # System design documentation
│   ├── PASSES_REDEMPTION_DESIGN.md # 🆕 Multi-instance design doc
│   ├── B2B_AFFILIATE_GUIDE.md      # B2B affiliate feature docs
│   ├── EVENT_FIELD_REFERENCE.md    # Field-level event documentation
│   ├── IMPLEMENTATION_SUMMARY.md   # Technical summary
│   ├── IMPLEMENTATION_PLAN.md      # Development roadmap
│   ├── CHANGELOG.md                # Version history
│   ├── CLEANUP_SUMMARY.md          # Refactoring notes
│   ├── SCHEMA_COMPATIBILITY_SUMMARY.md
│   ├── REFUND_TIMELINE_FIX.md
│   ├── REFUND_TIMELINE_SCHEMA_FIX.md
│   └── JSON_EDITOR_ENHANCEMENTS.md
│
└── PRD_user_stories_and_ac/        # Product requirements
    ├── assessment.md               # 🆕 Assessment criteria (converted from HTML)
    └── results-20251112-152412 - Sheet2.tsv  # Production data sample
```

## Key Concepts

### 1. Multi-Instance Payables 🆕

**Problem**: Some products (passes, multi-ride tickets) have 1 order + 1 order_detail but generate multiple supplier payables over time during fulfillment.

**Solution**: Use `fulfillment_instance_id` to scope payables:
- **Booking-level** (`fulfillment_instance_id=NULL`): Initial reservation, amount=0
- **Fulfillment-level** (e.g., `"ticket_code_1757809185001"`): Each redemption/leg with actual cost

**Example** (Entertainment Passes):
```
Order 1322884534, Detail 1359185528:
  - Booking (fulfillment_instance_id=NULL): 0 IDR
  - Redemption 1 (ticket_code_1757809185001): 127,500 IDR
  - Redemption 2 (ticket_code_1757809307001): 127,500 IDR
  - Redemption 3 (ticket_code_1757772769001): 127,500 IDR
Total: 382,500 IDR across 3 redemptions
```

**Query Pattern**:
```sql
-- Partition by fulfillment_instance_id to get separate instances
PARTITION BY order_id, order_detail_id, supplier_reference_id,
             COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__')
```

### 2. Party-Level Projection with Amount Effect 🆕

**Purpose**: Track multi-party obligations with directional effects.

**Amount Effect**:
- `INCREASES_PAYABLE`: We owe more (supplier cost, affiliate commission, tax, penalties)
- `DECREASES_PAYABLE`: We owe less (supplier commission retention, credits)

**Party Types**:
- `SUPPLIER`: Main supplier obligation (baseline from `supplier_timeline.amount`)
- `AFFILIATE`: B2B affiliate shareback/commission
- `TAX_AUTHORITY`: VAT, withholding tax
- `INTERNAL`: Platform costs (subsidies, operational fees)

**Calculation**:
```
Total Payable per Party = Baseline + Σ(INCREASES) - Σ(DECREASES)

Supplier Total = amount_due + INCREASES_PAYABLE - DECREASES_PAYABLE
Example: 150,000 + 0 - (20,025 + 2,475) = 127,500 IDR
```

**Status-Driven Logic**:
| Status | Baseline | Party Obligations Included |
|--------|----------|---------------------------|
| Confirmed, ISSUED, Invoiced | amount_due | ALL (timeline + standalone) |
| CancelledWithFee | 0 (fee in party lines) | Latest version only |
| CancelledNoFee, Voided | 0 | ONLY standalone (version=-1) |

### 3. Dual ID Strategy

Each pricing component has two IDs:

- **Semantic ID**: Stable logical identity across repricing/refunds
  - Format: `cs-{order_id}-{dimensions}-{component_type}`
  - Example: `cs-1322884534-OD-1359185528-BaseFare`
  - Used for: Aggregation, lineage tracking, refund matching

- **Instance ID**: Unique per snapshot occurrence
  - Format: `ci_{hash(semantic_id + snapshot_id)}`
  - Example: `ci_f0a1d2c3b4a50001`
  - Used for: Deduplication within snapshot, event correlation

### 4. Version Families

The system tracks **5 independent version dimensions**:

| Version Type | Scope | Example Key | Tracks |
|--------------|-------|-------------|--------|
| Pricing Snapshot | Per order | `pricing_snapshot_id` + `version` | Repricing events |
| Payment Timeline | Per order | `timeline_version` | Payment lifecycle |
| Supplier Timeline | Per order_detail | `supplier_timeline_version` | Supplier status |
| Refund Timeline | Per refund_id | `refund_timeline_version` | Refund lifecycle |
| Issuance Timeline | Per order_detail | `issuance_version` | Ticket issuance (future) |

Each family increments independently, enabling parallel evolution without conflicts.

### 5. Append-Only Architecture

- All changes create new versions (no updates or deletes)
- History is immutable for complete audit trail
- Refunds create new components with `refund_of_component_semantic_id` lineage pointer
- Enables time-travel queries and regulatory compliance

### 6. Component Granularity

Components can exist at different scopes via `dimensions`:

| Scope | Dimensions | Example Component |
|-------|-----------|-------------------|
| Order-level | `{}` | Platform fee, Order-level discount |
| Order detail-level | `{"order_detail_id": "OD-001"}` | Base fare per room/journey |
| Granular | `{"order_detail_id": "OD-001", "pax_id": "A1"}` | Per-passenger ancillary |
| Multi-dimensional | `{"order_detail_id": "OD-001", "leg_id": "CGK-SIN", "pax_id": "A1"}` | Per-leg per-passenger fare |

## Usage Examples

### Example 1: Simple Hotel Booking

1. Go to **Producer Playground** → **Pricing Events**
2. Select "Hotel 3-Night Booking (Simple)"
3. Click "Emit Event"
4. Go to **Order Explorer** → Select the order → View **Latest Pricing**

**Result**: See base fare, tax, and fee components with semantic IDs

### Example 2: Multi-Instance Passes Redemption 🆕

1. Go to **Producer Playground** → **Supplier & Payable Events**
2. Load files from `sample_events/supplier_and_payable_event/ttd-passes-prod-1322884534/`
3. Emit in sequence:
   - `001-booking-confirmed.json` (booking level, amount=0)
   - `002-redemption-1.json` (first redemption, ticket_code_1757809185001)
   - `003-redemption-2.json` (second redemption, ticket_code_1757809307001)
4. Go to **Order Explorer** → **Supplier Payables** tab

**Result**: See 3 separate payable instances:
- Booking: 0 IDR (fulfillment_instance_id=NULL)
- Redemption 1: 127,500 IDR (fulfillment_instance_id=ticket_code_1757809185001)
- Redemption 2: 127,500 IDR (fulfillment_instance_id=ticket_code_1757809307001)

Each instance shows party-level breakdown with amount_effect.

### Example 3: Payment with Loyalty Points 🆕

1. Emit a pricing event to create an order
2. Go to **Producer Playground** → **Payment Events**
3. Load `sample_events/payment_timeline/ttd-passes-prod-1322884534/001-captured.json`
4. Update `order_id` to match your order
5. Emit the event
6. Go to **Order Explorer** → **Payment Timeline**

**Result**: See payment captured with TIKETPOINT loyalty payment method, showing points used.

### Example 4: B2B Affiliate with Party Obligations

1. Go to **Producer Playground** → **Supplier & Payable Events**
2. Load `010-b2b-affiliate-supplier-issued-with-shareback.json` from `b2b-affiliate/` directory
3. Emit the event
4. Go to **Order Explorer** → **Supplier Payables**

**Result**: See multi-party payables:
- SUPPLIER party with base obligation
- AFFILIATE party with shareback amount (INCREASES_PAYABLE)

### Example 5: Out-of-Order Events (Stress Test)

1. Go to **Stress Tests** → "Out-of-Order Events"
2. Emit Version 3 first
3. Emit Version 2 second
4. Go to **Order Explorer** → **Version History**

**Result**: Both versions stored; latest view correctly shows v3

### Example 6: Payment Timeline

1. Emit a pricing event to create an order
2. Go to **Producer Playground** → **Payment Events**
3. Emit sequence: `010-checkout.json` → `020-authorized.json` → `030-captured.json`
4. Go to **Order Explorer** → **Payment Timeline**

**Result**: See complete payment lifecycle with timeline versions (v1 → v2 → v3)

## Database Schema

### Fact Tables (Append-Only)

**pricing_components_fact**:
- Dual IDs: `component_semantic_id`, `component_instance_id`
- Version keys: `pricing_snapshot_id`, `version`
- Dimensions: JSON (order_detail_id, pax_id, leg_id, etc.)
- Lineage: `refund_of_component_semantic_id`

**payment_timeline**:
- Version key: `timeline_version` (per order)
- Fields: status, payment_method, authorized_amount, captured_amount, instrument

**supplier_timeline**:
- Version key: `supplier_timeline_version` (per order_detail_id)
- 🆕 NEW: `fulfillment_instance_id` for multi-instance payables
- Fields: status, amount, amount_basis, currency, fx_context, entity_context

**supplier_payable_lines** 🆕:
- Links to: supplier_timeline via `supplier_timeline_version`
- 🆕 NEW: `fulfillment_instance_id` for multi-instance payables
- Fields: party_type, party_id, obligation_type, amount, amount_effect
- Version: -1 (standalone) or >= 1 (timeline-linked)

**refund_timeline**:
- Version key: `refund_timeline_version` (per refund_id)
- Fields: status, refund_amount, currency, refund_reason

**dlq** (Dead Letter Queue):
- Fields: event_id, error_type, error_message, raw_event, retry_count

### Derived Views (Latest State)

**order_pricing_latest**: Latest pricing per semantic_id
**payment_timeline_latest**: Latest payment status per order
**supplier_timeline_latest**: Latest supplier status per order_detail
**refund_timeline_latest**: Latest refund status per refund_id

### Indexes (Performance)

```sql
-- Multi-instance composite indexes 🆕
CREATE INDEX idx_supplier_timeline_multi_instance
  ON supplier_timeline(order_id, order_detail_id, supplier_reference_id, fulfillment_instance_id, supplier_timeline_version DESC);

CREATE INDEX idx_payable_lines_fulfillment
  ON supplier_payable_lines(order_id, order_detail_id, supplier_reference_id, fulfillment_instance_id, party_id, obligation_type);
```

## Testing

### Validation Tests

Test Pydantic schema validation in **Stress Tests** tab:
- Invalid component types → DLQ
- Missing required fields → DLQ
- Invalid enum values → DLQ
- Negative amounts → Valid for Subsidy, Discount, Refund

### Edge Cases

- **Out-of-order events** (v3 before v2) → Both stored, latest view correct
- **Duplicate event IDs** → Currently allowed (production should add constraint)
- **Version gaps** (v1 → v3) → Accepted but could be monitored
- **NULL fulfillment_instance_id** → Treated as single-instance (backward compatible)
- **Empty parties array** → Projection-based (obligations carried forward)

### Debug Tools

**debug_multi_instance.py** 🆕:
```bash
python debug_multi_instance.py
```
- Emits test events (booking + 2 redemptions)
- Inspects database state (supplier_timeline, supplier_payable_lines)
- Verifies get_total_effective_payables() result
- Validates multi-instance splitting

## Production Considerations

This prototype demonstrates core concepts. For production:

1. **Database**: Replace SQLite with production database (Spanner, PostgreSQL, BigQuery)
2. **Event Bus**: Integrate with Kafka/Pub/Sub for real event consumption
3. **Schema Registry**: Use Avro/Protobuf for event evolution
4. **Idempotency**: Add unique constraint on `(event_id, idempotency_key)`
5. **Monitoring**: Add metrics, traces, alerts (OpenTelemetry)
6. **Retry Logic**: Implement exponential backoff for DLQ
7. **Data Retention**: Define hot/warm/cold archival policies
8. **Access Control**: Add authentication, authorization, audit logs
9. **Performance**: Add caching, read replicas, query optimization
10. **Disaster Recovery**: Backups, point-in-time recovery, multi-region

## Troubleshooting

### App won't start
- Ensure Python 3.12+ is installed: `python --version`
- Activate virtual environment: `source venv/bin/activate`
- Install dependencies: `pip install -r requirements.txt`

### Database errors
- Delete `data/uprl.db` and restart (will reinitialize schema)
- Or use **Settings** → "Clear All Data" in the app
- Check migration logs for schema evolution issues

### Events not appearing
- Check **Ingestion Console** for DLQ entries
- Verify JSON format in Producer Playground
- Ensure required fields are present (`event_id`, `order_id`, `emitted_at`)
- Check Pydantic model matches event structure

### Multi-instance payables not splitting 🆕
- Verify `fulfillment_instance_id` field exists in `Supplier` Pydantic model (src/models/events.py:286)
- Check database: `SELECT fulfillment_instance_id FROM supplier_timeline WHERE order_id='...'`
- Run debug script: `python debug_multi_instance.py`
- Verify UI detection: Check `has_multi_instance` logic in order_explorer.py

### Party-level projection incorrect 🆕
- Check `amount_effect` values (INCREASES_PAYABLE / DECREASES_PAYABLE)
- Verify supplier status (affects obligation inclusion rules)
- Inspect `supplier_payable_lines` table for party obligations
- Check standalone adjustments (version=-1) vs timeline-linked (version >= 1)

## Documentation

### Core Documentation
- **README.md** (this file): Quick start and feature overview
- **CLAUDE.md**: Comprehensive AI guidance (file structure, common tasks, debug strategies)
- **QUICKSTART.md**: 5-minute getting started guide

### Technical Documentation (see `docs/` directory)
- **ARCHITECTURE.md**: System design, data flow, event processing
- **PASSES_REDEMPTION_DESIGN.md** 🆕: Multi-instance payables design
- **B2B_AFFILIATE_GUIDE.md**: B2B affiliate tracking feature
- **EVENT_FIELD_REFERENCE.md**: Field-level event documentation
- **SCHEMA_COMPATIBILITY_SUMMARY.md**: Schema evolution guide
- **CHANGELOG.md**: Version history and feature additions

### Assessment & Requirements
- **PRD_user_stories_and_ac/assessment.md** 🆕: Acceptance criteria (converted from HTML)
- Original PRD documents in parent directories

## Contributing

This is an educational prototype. For production implementation:
- **Order Platform Engineering** team: Core ingestion pipeline
- **Finance/EDP** stakeholders: Payable calculation rules
- **Vertical service owners**: Event schema design
- **Data Platform** team: Production database and streaming

## License

Internal use - Tiket.com Order Platform team

---

## Quick Links

- 🏠 [Home](app.py): Start the Streamlit app
- 📚 [CLAUDE.md](CLAUDE.md): Comprehensive AI guidance
- 🏗️ [Architecture](docs/ARCHITECTURE.md): System design
- 🎟️ [Multi-Instance Design](docs/PASSES_REDEMPTION_DESIGN.md): Passes redemption
- 🧪 [Tests](tests/README.md): Test documentation
- 📊 [Assessment](PRD_user_stories_and_ac/assessment.md): Acceptance criteria

---

**Built with**: Streamlit, SQLite, Pydantic, Python 3.12+
**Purpose**: Educational demonstration of event-driven pricing architecture
**Version**: 2.0.0 (Multi-Instance Payables)
**Last Updated**: 2025-11-13
