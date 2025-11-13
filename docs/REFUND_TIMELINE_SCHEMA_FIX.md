# Refund Timeline Schema Restructuring

## Issues Fixed

### 1. ✅ Nested Expanders Error
**Problem**: StreamlitAPIException - expanders cannot be nested
**Cause**: `render_refund_timeline_tab()` had an expander inside another expander
**Fix**: Removed nested "📋 View Raw Event Details" expander from inside refund_id expander

### 2. ✅ Incorrect Producer Schema
**Problem**: `refund_timeline_version` was in producer events (should be assigned by Order Core)
**Cause**: Mixing producer responsibility with Order Core normalization responsibility
**Fix**:
- Removed `refund_timeline_version` from `RefundLifecycleEvent` (producer model)
- Order Core now assigns version during ingestion (auto-increments per refund_id)
- Added `status` field to producer events

### 3. ✅ Missing Status Field
**Problem**: No status field to track refund state machine
**Cause**: Schema only had `event_type`, not clear current state
**Fix**: Added `status` field with values: INITIATED, PROCESSING, ISSUED, CLOSED, FAILED

### 4. ✅ Renamed "Unified Order View"
**Problem**: Name didn't clearly convey "latest state" concept
**Fix**: Renamed to "Latest State Projection" throughout app

## Schema Changes

### Producer Event Schema (RefundLifecycleEvent)

**Before**:
```json
{
  "event_type": "refund.initiated",
  "order_id": "ORD-NEW",
  "refund_id": "RFD-001",
  "refund_timeline_version": 1,  // ❌ Should not be here
  "refund_amount": 500000,
  "currency": "IDR",
  "refund_reason": "Customer requested cancellation",
  "emitted_at": "2025-11-10T12:00:00Z",
  "emitter_service": "refund-service"
}
```

**After**:
```json
{
  "event_type": "refund.initiated",
  "order_id": "ORD-NEW",
  "refund_id": "RFD-001",
  "status": "INITIATED",  // ✅ NEW: Clear state indicator
  "refund_amount": 500000,
  "currency": "IDR",
  "refund_reason": "Customer requested cancellation",
  "emitted_at": "2025-11-10T12:00:00Z",
  "emitter_service": "refund-service"
}
```

### Database Schema (refund_timeline table)

**Added**:
- `status TEXT NOT NULL` column after `event_type`

**Note**: `refund_timeline_version` remains in database (assigned by Order Core)

### Normalized Event Schema (NormalizedRefundTimeline)

**Added**:
- `status: str` field
- Comment clarifying version is assigned by Order Core

## Status Field Values

| Status | Emoji | Meaning | Event Type Example |
|--------|-------|---------|-------------------|
| **INITIATED** | 🔄 | Refund request created | `refund.initiated` |
| **PROCESSING** | ⏳ | Refund being processed | `refund.processing` |
| **ISSUED** | ✅ | Refund successfully issued | `refund.issued` |
| **CLOSED** | 🔒 | Refund completed/finalized | `refund.closed` |
| **FAILED** | ❌ | Refund failed/rejected | `refund.failed` |

## Version Assignment Logic

**Order Core Ingestion** (`_ingest_refund_lifecycle` method):

```python
# Get latest version for this refund_id and increment
cursor.execute("""
    SELECT MAX(refund_timeline_version)
    FROM refund_timeline
    WHERE order_id = ? AND refund_id = ?
""", (event.order_id, event.refund_id))
max_version = cursor.fetchone()[0]
refund_timeline_version = (max_version or 0) + 1
```

**Result**: Auto-incrementing version per (order_id, refund_id) pair

## Files Modified

### 1. Database Layer
**File**: `src/storage/database.py`
- Added `status TEXT NOT NULL` to schema (line 167)
- Updated `insert_refund_timeline()` to include status (line 329)
- Updated `get_refund_timeline()` query to SELECT status (line 497)

### 2. Event Models
**File**: `src/models/events.py`
- Removed `refund_timeline_version` from `RefundLifecycleEvent` (line 337)
- Added `status: str` field (line 337)
- Added doc comment explaining version assignment (lines 327-330)

**File**: `src/models/normalized.py`
- Added `status: str` to `NormalizedRefundTimeline` (line 94)

### 3. Ingestion Pipeline
**File**: `src/ingestion/pipeline.py`
- Added version assignment logic (lines 780-789)
- Updated to read `status` from producer event (line 797)
- Removed reading `refund_timeline_version` from event

### 4. UI - Producer Playground
**File**: `src/ui/producer_playground.py`
- Updated default template to remove `refund_timeline_version` (removed line 321)
- Added `status: "INITIATED"` with comment (line 321)

### 5. UI - Unified Order View (now Latest State Projection)
**File**: `src/ui/unified_order_view.py`
- Renamed title to "Latest State Projection" (line 14)
- Added status display with emoji (lines 344-351)
- Updated metrics to show Status first (lines 353-361)
- Added status column to timeline table (lines 369-384)

**File**: `app.py`
- Renamed "Unified Order View" → "Latest State Projection" (lines 86, 106, 234)

### 6. UI - Order Explorer
**File**: `src/ui/order_explorer.py`
- Added "↩️ Refund Timeline" tab (line 37)
- Fixed nested expanders (removed lines 650-665)
- Added status display with emoji (lines 606-613)
- Updated metrics to show Status first (lines 615-623)
- Added status column to timeline table (lines 632-648)

### 7. Sample Events
**Created**:
- `sample_events/refund_timeline/1_initiated.json` - Status: INITIATED
- `sample_events/refund_timeline/2_processing.json` - Status: PROCESSING
- `sample_events/refund_timeline/3_issued.json` - Status: ISSUED
- `sample_events/refund_timeline/4_closed.json` - Status: CLOSED

## Migration Notes

### Database Migration
**No migration needed** - old database can be deleted and recreated:
```bash
rm -f data/uprl.db
```

The schema will be recreated on next app start with the new `status` column.

### Event Replay
If you need to replay old events:
1. Old events with `refund_timeline_version` will fail validation (expected)
2. Update old events to remove `refund_timeline_version` and add `status`
3. Re-emit updated events

## Testing

### How to Test

1. **Clear old database**:
   ```bash
   rm -f data/uprl.db
   ```

2. **Start app**: `./run.sh` or refresh browser

3. **Emit refund timeline events**:
   - Go to **Producer Playground** → **Refund** → **📅 Refund Timeline**
   - Load events in order:
     - `1_initiated.json` - Creates RFD-001 version 1
     - `2_processing.json` - Creates RFD-001 version 2
     - `3_issued.json` - Creates RFD-001 version 3
     - `4_closed.json` - Creates RFD-001 version 4

4. **View refund timeline**:
   - **Order Explorer** → ↩️ Refund Timeline tab
   - **Latest State Projection** → ↩️ Refund Timeline section

### Expected Results

**Order Explorer - Refund Timeline Tab**:
- Refund ID shown as expandable section
- Metrics show:
  - Status: 🔒 CLOSED (latest)
  - Version: 4
  - Event Type: refund.closed
  - Refund Amount: IDR 500,000
- Timeline table shows 4 rows with Status column

**Latest State Projection - Refund Timeline Section**:
- Same display as Order Explorer
- Integrated with pricing, payment, and supplier timelines

**Raw Data Storage**:
- `refund_timeline` table shows `status` column
- Versions auto-increment: 1, 2, 3, 4

## Benefits

### 1. Clear Separation of Concerns
- **Producer**: Emits events with business state (`status`)
- **Order Core**: Assigns technical versioning (`refund_timeline_version`)

### 2. Better Status Visibility
- Status field makes refund state immediately clear
- Emoji indicators provide visual feedback
- Supports refund state machine validation (future)

### 3. Proper Schema Evolution
- Producer events don't contain normalization artifacts
- Follows same pattern as supplier/payment timelines
- Enables independent evolution of producer and Order Core

### 4. Better UX
- Status shown prominently in all views
- Clear lifecycle progression (INITIATED → PROCESSING → ISSUED → CLOSED)
- Failed refunds easily identifiable (FAILED status)

## Future Enhancements

Potential improvements:
- [ ] Validate state transitions (INITIATED can only go to PROCESSING or FAILED)
- [ ] Link refund timeline to refund components (by refund_id)
- [ ] Add refund_initiated_by field (user_id or system)
- [ ] Add refund_approved_by field for manual approvals
- [ ] Export refund lifecycle report
- [ ] Refund SLA tracking (time from INITIATED to ISSUED)
