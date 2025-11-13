# Refund Timeline Display Fix

## Problem
Refund timeline data was not appearing in **Order Explorer** or **Unified Order View**, even though:
- ✅ `refund_timeline` table exists in database
- ✅ `insert_refund_timeline()` method exists
- ✅ Refund events can be emitted from Producer Playground
- ✅ Raw Storage Viewer shows refund data

## Root Cause

1. **Missing Query Method**: No `get_refund_timeline()` method in database.py
2. **Missing UI Sections**: No refund timeline rendering in order_explorer.py and unified_order_view.py

## Solution

### 1. Added Database Query Method

**File**: `src/storage/database.py` (line 490-503)

```python
def get_refund_timeline(self, order_id: str):
    """Get refund timeline for an order (all refunds, all versions, ordered by refund_id and version)"""
    cursor = self.conn.cursor()
    cursor.execute("""
        SELECT
            event_id, order_id, refund_id, refund_timeline_version,
            event_type, refund_amount, currency, refund_reason,
            emitter_service, ingested_at, emitted_at, metadata
        FROM refund_timeline
        WHERE order_id = ?
        ORDER BY refund_id ASC, refund_timeline_version ASC
    """, (order_id,))
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
```

### 2. Added Refund Timeline to Unified Order View

**File**: `src/ui/unified_order_view.py`

#### A. Updated Main Rendering Function (line 42-58)
Added two new sections:
- **Section 3**: Payment Timeline (full history, not just latest state)
- **Section 5**: Refund Timeline

#### B. Added `render_payment_timeline_section()` (line 263-316)
Shows complete payment timeline evolution with:
- Timeline version tracking
- Event type (payment.authorized, payment.captured, etc.)
- Status transitions
- Authorized and captured amounts
- Expandable event details with instrument JSON

#### C. Added `render_refund_timeline_section()` (line 319-367)
Shows refund lifecycle with:
- Grouping by `refund_id` (supports multiple refunds per order)
- Latest status metrics (version, event type, amount)
- Timeline table showing all events
- Refund reason display

### 3. Added Refund Timeline Tab to Order Explorer

**File**: `src/ui/order_explorer.py`

#### A. Added New Tab (line 31-39)
Changed from 6 tabs to 7 tabs, adding "↩️ Refund Timeline" between Supplier Timeline and Supplier Payables

#### B. Added `render_refund_timeline_tab()` (line 580-665)
Comprehensive refund display with:
- Emoji indicators for event types:
  - 🔄 `refund.initiated`
  - ✅ `refund.issued`
  - 🔒 `refund.closed`
  - ❌ `refund.failed`
- Metrics: version, event type, amount, emitted_at
- Refund reason highlighting
- Event timeline table with emitter service
- Expandable raw event JSON details

## Features

### Refund Timeline Display

**Data Shown**:
- `refund_id` - Unique refund identifier
- `refund_timeline_version` - Monotonic version per refund
- `event_type` - Lifecycle events (initiated, issued, closed, failed)
- `refund_amount` - Amount refunded (with proper currency formatting)
- `currency` - Refund currency code
- `refund_reason` - Human-readable reason
- `emitter_service` - Service that generated the event
- `emitted_at` - Timestamp of event

**Grouping**:
- Refunds are grouped by `refund_id`
- Each refund shows its complete version history
- Supports multiple refunds per order (e.g., partial refunds)

**Visual Indicators**:
- Status emojis for event types
- Color-coded metrics
- Expandable sections for detailed views

## Testing

### How to Test

1. **Start the app**: `./run.sh` or `streamlit run app.py`

2. **Emit a refund event**:
   - Go to **Producer Playground** tab
   - Select **Refund** category
   - Choose **Refund Timeline** sub-tab
   - Load sample event: `1_initiated.json`
   - Click **📤 Emit Event**

3. **View refund timeline**:
   - **Order Explorer** → Select order → **↩️ Refund Timeline** tab
   - **Unified Order View** → Select order → Scroll to **↩️ Refund Timeline** section

### Sample Refund Events

Located in: `sample_events/refund_timeline/`

- `1_initiated.json` - Refund request initiated
- `2_issued.json` - Refund processed/issued
- `3_closed.json` - Refund completed/closed

Each event increments `refund_timeline_version` to track lifecycle.

## Files Modified

1. **src/storage/database.py** - Added `get_refund_timeline()` method
2. **src/ui/unified_order_view.py** - Added refund and payment timeline sections
3. **src/ui/order_explorer.py** - Added refund timeline tab

## Related Components

### Refund Components vs Refund Timeline

**Different but complementary**:

1. **Refund Timeline** (what we fixed):
   - **Table**: `refund_timeline`
   - **Purpose**: Track refund lifecycle events (initiated → issued → closed)
   - **Schema**: `refund_id`, `refund_timeline_version`, `event_type`, `refund_amount`, `refund_reason`
   - **Display**: Timeline view showing event progression

2. **Refund Components** (already working):
   - **Table**: `pricing_components_fact` (where `is_refund = 1`)
   - **Purpose**: Price component lineage (which original components were refunded)
   - **Schema**: Includes `refund_of_component_semantic_id` for lineage
   - **Display**: Shown in "💰 Latest Breakdown" tab with lineage links

Both are needed for complete refund tracking:
- **Timeline** = operational lifecycle
- **Components** = financial impact and lineage

## Deployment Notes

No database migrations needed - the `refund_timeline` table already existed. This was purely a query/UI addition.

## Future Enhancements

Potential improvements:
- [ ] Link refund timeline events to refund components (cross-reference by `refund_id`)
- [ ] Add refund state machine validation (ensure events follow proper lifecycle)
- [ ] Add refund amount reconciliation check (timeline amount vs component amount)
- [ ] Export refund timeline to CSV
- [ ] Add filtering by date range or event type
