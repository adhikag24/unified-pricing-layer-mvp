"""
SQLite database initialization and management.
Implements append-only fact tables and derived views.
"""
import sqlite3
from pathlib import Path
from typing import Optional
import json


class Database:
    """SQLite database wrapper for prototype"""

    def __init__(self, db_path: str = "data/uprl.db"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row  # Enable column access by name
        return self.conn

    def _ensure_connected(self):
        """Ensure database connection is open, reconnect if needed"""
        if not self.conn:
            self.connect()
            return

        # Check if connection is still alive
        try:
            self.conn.execute("SELECT 1")
        except (sqlite3.ProgrammingError, sqlite3.OperationalError):
            # Connection is closed or broken, reconnect
            self.connect()

    def _run_migrations(self, cursor):
        """Run schema migrations for existing databases"""

        # Helper function to check if table exists
        def table_exists(table_name):
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table_name,)
            )
            return cursor.fetchone() is not None

        # Migration 1: Add fulfillment_instance_id to supplier_timeline (2025-11-13)
        if table_exists('supplier_timeline'):
            try:
                cursor.execute("SELECT fulfillment_instance_id FROM supplier_timeline LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                print("🔄 Running migration: Adding fulfillment_instance_id to supplier_timeline...")
                cursor.execute("ALTER TABLE supplier_timeline ADD COLUMN fulfillment_instance_id TEXT")
                self.conn.commit()
                print("✅ Migration complete: supplier_timeline.fulfillment_instance_id added")

        # Migration 2: Add fulfillment_instance_id to supplier_payable_lines (2025-11-13)
        if table_exists('supplier_payable_lines'):
            try:
                cursor.execute("SELECT fulfillment_instance_id FROM supplier_payable_lines LIMIT 1")
            except sqlite3.OperationalError:
                # Column doesn't exist, add it
                print("🔄 Running migration: Adding fulfillment_instance_id to supplier_payable_lines...")
                cursor.execute("ALTER TABLE supplier_payable_lines ADD COLUMN fulfillment_instance_id TEXT")
                self.conn.commit()
                print("✅ Migration complete: supplier_payable_lines.fulfillment_instance_id added")

    def initialize_schema(self):
        """Create all tables and views with migration support"""
        if not self.conn:
            self.connect()

        cursor = self.conn.cursor()

        # Run migrations before creating tables
        self._run_migrations(cursor)

        # Append-only fact table: Pricing Components
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS pricing_components_fact (
                component_semantic_id TEXT NOT NULL,
                component_instance_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                pricing_snapshot_id TEXT NOT NULL,
                version INTEGER NOT NULL,
                component_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                dimensions TEXT NOT NULL,  -- JSON
                description TEXT,
                is_refund INTEGER NOT NULL DEFAULT 0,  -- 0=false, 1=true
                refund_of_component_semantic_id TEXT,
                emitter_service TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                emitted_at TEXT NOT NULL,
                metadata TEXT  -- JSON
            )
        """)

        # Index for querying by order and version
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pricing_order_version
            ON pricing_components_fact(order_id, version DESC)
        """)

        # Index for semantic ID lookups (lineage tracing)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_pricing_semantic
            ON pricing_components_fact(component_semantic_id)
        """)

        # Append-only fact table: Payment Timeline
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payment_timeline (
                event_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                timeline_version INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,  -- "Authorized", "Captured", "Refunded"
                payment_method TEXT NOT NULL,
                payment_intent_id TEXT,  -- For BNPL, retries tracking
                authorized_amount INTEGER,
                captured_amount INTEGER,  -- Amount captured in this specific event
                captured_amount_total INTEGER,  -- Running total of all captures
                amount INTEGER NOT NULL,  -- Legacy field (backward compatibility)
                currency TEXT NOT NULL,
                instrument_json TEXT,  -- JSON string of masked instrument details
                pg_reference_id TEXT,
                emitter_service TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                emitted_at TEXT NOT NULL,
                metadata TEXT  -- JSON
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_order_version
            ON payment_timeline(order_id, timeline_version DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payment_order_status
            ON payment_timeline(order_id, status, timeline_version DESC)
        """)

        # Append-only fact table: Supplier Timeline
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supplier_timeline (
                event_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                order_detail_id TEXT NOT NULL,
                supplier_timeline_version INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                supplier_id TEXT NOT NULL,
                booking_code TEXT,
                supplier_reference_id TEXT,
                fulfillment_instance_id TEXT,  -- NEW: For multi-instance payables (passes, multi-ride, etc.)
                amount INTEGER,
                amount_basis TEXT,  -- "gross", "net", or "redemption-triggered"
                currency TEXT,
                status TEXT,
                cancellation_fee_amount INTEGER,
                cancellation_fee_currency TEXT,
                fx_context TEXT,  -- JSON: FX rates and currencies
                entity_context TEXT,  -- JSON: Entity/legal context
                emitter_service TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                emitted_at TEXT NOT NULL,
                metadata TEXT  -- JSON
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_supplier_order_detail_version
            ON supplier_timeline(order_id, order_detail_id, supplier_timeline_version DESC)
        """)

        # New composite index for multi-instance payables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_supplier_fulfillment_instance
            ON supplier_timeline(order_id, order_detail_id, supplier_reference_id, fulfillment_instance_id, supplier_timeline_version DESC)
        """)

        # Append-only fact table: Supplier Payable Lines (multi-party breakdown)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS supplier_payable_lines (
                line_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                order_id TEXT NOT NULL,
                order_detail_id TEXT NOT NULL,
                supplier_reference_id TEXT,  -- Booking code/reference for scoped projection
                fulfillment_instance_id TEXT,  -- NEW: For multi-instance payables (passes, multi-ride, etc.)
                supplier_timeline_version INTEGER NOT NULL,
                obligation_type TEXT NOT NULL,
                party_type TEXT,  -- "SUPPLIER", "AFFILIATE", "TAX_AUTHORITY", "INTERNAL"
                party_id TEXT NOT NULL,
                party_name TEXT,
                amount INTEGER NOT NULL,
                amount_effect TEXT NOT NULL DEFAULT 'INCREASES_PAYABLE',  -- "INCREASES_PAYABLE" or "DECREASES_PAYABLE"
                currency TEXT NOT NULL,
                calculation_basis TEXT,
                calculation_rate REAL,
                calculation_description TEXT,
                ingested_at TEXT NOT NULL,
                metadata TEXT
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payable_lines_order
            ON supplier_payable_lines(order_id, order_detail_id, supplier_timeline_version DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payable_lines_supplier_ref
            ON supplier_payable_lines(order_id, order_detail_id, supplier_reference_id, party_id, obligation_type)
        """)

        # New composite index for multi-instance payables
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_payable_lines_fulfillment
            ON supplier_payable_lines(order_id, order_detail_id, supplier_reference_id, fulfillment_instance_id, party_id, obligation_type)
        """)

        # Append-only fact table: Refund Timeline
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS refund_timeline (
                event_id TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                refund_id TEXT NOT NULL,
                refund_timeline_version INTEGER NOT NULL,
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,  -- INITIATED, PROCESSING, ISSUED, CLOSED, FAILED
                refund_amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                refund_reason TEXT,
                emitter_service TEXT NOT NULL,
                ingested_at TEXT NOT NULL,
                emitted_at TEXT NOT NULL,
                metadata TEXT  -- JSON
            )
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_refund_order_refund_version
            ON refund_timeline(order_id, refund_id, refund_timeline_version DESC)
        """)

        # Dead Letter Queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dlq (
                dlq_id TEXT PRIMARY KEY,
                event_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                order_id TEXT,
                raw_event TEXT NOT NULL,
                error_type TEXT NOT NULL,
                error_message TEXT NOT NULL,
                failed_at TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0
            )
        """)

        # Derived view: Latest Pricing Breakdown (per semantic component)
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS order_pricing_latest AS
            SELECT * FROM pricing_components_fact
            WHERE (order_id, component_semantic_id, version) IN (
                SELECT order_id, component_semantic_id, MAX(version)
                FROM pricing_components_fact
                GROUP BY order_id, component_semantic_id
            )
        """)

        # Derived view: Latest Payment Status
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS payment_timeline_latest AS
            SELECT * FROM payment_timeline
            WHERE (order_id, timeline_version) IN (
                SELECT order_id, MAX(timeline_version)
                FROM payment_timeline
                GROUP BY order_id
            )
        """)

        # Derived view: Latest Supplier Status per Order Detail
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS supplier_timeline_latest AS
            SELECT * FROM supplier_timeline
            WHERE (order_id, order_detail_id, supplier_timeline_version) IN (
                SELECT order_id, order_detail_id, MAX(supplier_timeline_version)
                FROM supplier_timeline
                GROUP BY order_id, order_detail_id
            )
        """)

        # Derived view: Latest Refund Status per Refund ID
        cursor.execute("""
            CREATE VIEW IF NOT EXISTS refund_timeline_latest AS
            SELECT * FROM refund_timeline
            WHERE (order_id, refund_id, refund_timeline_version) IN (
                SELECT order_id, refund_id, MAX(refund_timeline_version)
                FROM refund_timeline
                GROUP BY order_id, refund_id
            )
        """)

        self.conn.commit()

    def insert_pricing_component(self, component: dict):
        """Insert normalized pricing component"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO pricing_components_fact VALUES (
                :component_semantic_id, :component_instance_id, :order_id,
                :pricing_snapshot_id, :version, :component_type, :amount,
                :currency, :dimensions, :description, :is_refund, :refund_of_component_semantic_id,
                :emitter_service, :ingested_at, :emitted_at, :metadata
            )
        """, {
            **component,
            'dimensions': json.dumps(component['dimensions']),
            'is_refund': 1 if component.get('is_refund') else 0,  # Convert bool to SQLite INTEGER
            'metadata': json.dumps(component.get('metadata'))
        })
        self.conn.commit()

    def insert_payment_timeline(self, entry: dict):
        """Insert payment timeline entry"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO payment_timeline VALUES (
                :event_id, :order_id, :timeline_version, :event_type, :status,
                :payment_method, :payment_intent_id, :authorized_amount,
                :captured_amount, :captured_amount_total, :amount, :currency,
                :instrument_json, :pg_reference_id,
                :emitter_service, :ingested_at, :emitted_at, :metadata
            )
        """, {
            **entry,
            'instrument_json': entry.get('instrument_json'),  # JSON string or None
            'metadata': json.dumps(entry.get('metadata'))
        })
        self.conn.commit()

    def insert_supplier_timeline(self, entry: dict):
        """Insert supplier timeline entry (supports both v1 and v2 schema + multi-instance)"""
        self._ensure_connected()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO supplier_timeline VALUES (
                :event_id, :order_id, :order_detail_id, :supplier_timeline_version,
                :event_type, :supplier_id, :booking_code, :supplier_reference_id, :fulfillment_instance_id, :amount,
                :amount_basis, :currency, :status, :cancellation_fee_amount, :cancellation_fee_currency,
                :fx_context, :entity_context,
                :emitter_service, :ingested_at, :emitted_at, :metadata
            )
        """, {
            **entry,
            'booking_code': entry.get('booking_code'),
            'fulfillment_instance_id': entry.get('fulfillment_instance_id'),  # NEW: Multi-instance payables
            'amount_basis': entry.get('amount_basis'),  # "gross", "net", or "redemption-triggered"
            'status': entry.get('status'),
            'cancellation_fee_amount': entry.get('cancellation_fee_amount'),
            'cancellation_fee_currency': entry.get('cancellation_fee_currency'),
            'fx_context': entry.get('fx_context'),  # JSON string
            'entity_context': entry.get('entity_context'),  # JSON string
            'metadata': json.dumps(entry.get('metadata')) if entry.get('metadata') else None
        })
        self.conn.commit()

    def insert_payable_line(self, entry: dict):
        """Insert supplier payable line (supports both v1 and v2 schema with amount_effect, party_type, and multi-instance)"""
        self._ensure_connected()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO supplier_payable_lines VALUES (
                :line_id, :event_id, :order_id, :order_detail_id, :supplier_reference_id, :fulfillment_instance_id, :supplier_timeline_version,
                :obligation_type, :party_type, :party_id, :party_name, :amount, :amount_effect, :currency,
                :calculation_basis, :calculation_rate, :calculation_description,
                :ingested_at, :metadata
            )
        """, {
            **entry,
            'supplier_reference_id': entry.get('supplier_reference_id'),  # Booking-scoped projection
            'fulfillment_instance_id': entry.get('fulfillment_instance_id'),  # NEW: Multi-instance payables
            'party_type': entry.get('party_type'),  # Party type field
            'amount_effect': entry.get('amount_effect', 'INCREASES_PAYABLE'),  # Default to INCREASES_PAYABLE for v1
            'metadata': json.dumps(entry.get('metadata')) if entry.get('metadata') else None
        })
        self.conn.commit()

    def insert_refund_timeline(self, entry: dict):
        """Insert refund timeline entry"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO refund_timeline VALUES (
                :event_id, :order_id, :refund_id, :refund_timeline_version,
                :event_type, :status, :refund_amount, :currency, :refund_reason,
                :emitter_service, :ingested_at, :emitted_at, :metadata
            )
        """, {
            **entry,
            'metadata': json.dumps(entry.get('metadata'))
        })
        self.conn.commit()

    def insert_dlq(self, dlq_entry: dict):
        """Insert DLQ entry"""
        self._ensure_connected()
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO dlq VALUES (
                :dlq_id, :event_id, :event_type, :order_id, :raw_event,
                :error_type, :error_message, :failed_at, :retry_count
            )
        """, dlq_entry)
        self.conn.commit()

    def get_order_pricing_latest(self, order_id: str):
        """Get latest pricing breakdown for an order"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT * FROM order_pricing_latest
            WHERE order_id = ?
            ORDER BY component_type, dimensions
        """, (order_id,))
        return cursor.fetchall()

    def get_order_pricing_history(self, order_id: str):
        """Get all pricing versions for an order"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT version, pricing_snapshot_id, COUNT(*) as component_count,
                   SUM(amount) as total_amount, currency, emitted_at
            FROM pricing_components_fact
            WHERE order_id = ?
            GROUP BY version, pricing_snapshot_id, currency, emitted_at
            ORDER BY version DESC
        """, (order_id,))
        return cursor.fetchall()

    def get_component_lineage(self, semantic_id: str):
        """
        Trace component lineage including refunds.

        Updated: Refunds now have DIFFERENT semantic_ids (include refund_id).
        We find refunds by matching refund_of_component_semantic_id to the original's semantic_id.
        """
        cursor = self.conn.cursor()
        # Get original component occurrences (is_refund=0)
        cursor.execute("""
            SELECT * FROM pricing_components_fact
            WHERE component_semantic_id = ? AND is_refund = 0
            ORDER BY version ASC
        """, (semantic_id,))
        original = cursor.fetchall()

        # Get refund components that reference this original component
        # Refunds have different semantic_ids but link back via refund_of_component_semantic_id
        cursor.execute("""
            SELECT * FROM pricing_components_fact
            WHERE refund_of_component_semantic_id = ? AND is_refund = 1
            ORDER BY version ASC
        """, (semantic_id,))
        refunds = cursor.fetchall()

        return {'original': original, 'refunds': refunds}

    def get_all_orders(self):
        """Get list of all orders in the system from ANY event type"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT DISTINCT order_id FROM (
                SELECT order_id FROM pricing_components_fact
                UNION
                SELECT order_id FROM payment_timeline
                UNION
                SELECT order_id FROM supplier_timeline
                UNION
                SELECT order_id FROM refund_timeline
            )
            ORDER BY order_id
        """)
        return [row[0] for row in cursor.fetchall()]

    # Version retrieval methods for normalization layer
    def get_latest_pricing_version(self, order_id: str) -> int:
        """
        Get the latest pricing version for an order.
        Used by normalization layer to assign monotonic version numbers.
        Returns None if no previous versions exist.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT MAX(version) FROM pricing_components_fact
            WHERE order_id = ?
        """, (order_id,))
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else None

    def get_latest_payment_timeline_version(self, order_id: str) -> int:
        """
        Get the latest payment timeline version for an order.
        Used by normalization layer to assign monotonic timeline_version numbers.
        Returns None if no previous versions exist.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT MAX(timeline_version) FROM payment_timeline
            WHERE order_id = ?
        """, (order_id,))
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else None

    def get_latest_supplier_timeline_version(self, order_id: str, order_detail_id: str) -> int:
        """
        Get the latest supplier timeline version for an order_detail.
        Used by normalization layer to assign monotonic supplier_timeline_version numbers.
        Returns None if no previous versions exist.
        """
        self._ensure_connected()
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT MAX(supplier_timeline_version) FROM supplier_timeline
            WHERE order_id = ? AND order_detail_id = ?
        """, (order_id, order_detail_id))
        result = cursor.fetchone()
        return result[0] if result and result[0] is not None else None

    def get_payment_timeline(self, order_id: str):
        """Get payment timeline for an order (all versions, ordered by timeline_version)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                event_id, order_id, timeline_version, event_type, status,
                payment_method, payment_intent_id, authorized_amount,
                captured_amount, captured_amount_total, amount, currency,
                instrument_json, pg_reference_id,
                emitter_service, ingested_at, emitted_at, metadata
            FROM payment_timeline
            WHERE order_id = ?
            ORDER BY timeline_version ASC
        """, (order_id,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_supplier_timeline(self, order_id: str, order_detail_id: str):
        """Get supplier timeline for an order_detail (all versions, ordered by supplier_timeline_version)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                event_id, order_id, order_detail_id, supplier_timeline_version,
                event_type, supplier_id, supplier_reference_id, amount,
                currency, status, cancellation_fee_amount, cancellation_fee_currency,
                emitter_service, ingested_at, emitted_at, metadata
            FROM supplier_timeline
            WHERE order_id = ? AND order_detail_id = ?
            ORDER BY supplier_timeline_version ASC
        """, (order_id, order_detail_id))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_refund_timeline(self, order_id: str):
        """Get refund timeline for an order (all refunds, all versions, ordered by refund_id and version)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                event_id, order_id, refund_id, refund_timeline_version,
                event_type, status, refund_amount, currency, refund_reason,
                emitter_service, ingested_at, emitted_at, metadata
            FROM refund_timeline
            WHERE order_id = ?
            ORDER BY refund_id ASC, refund_timeline_version ASC
        """, (order_id,))
        columns = [desc[0] for desc in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_supplier_payables_latest(self, order_id: str):
        """
        Get all supplier payable lines for an order (append-only, cumulative).
        Returns ALL lines across timeline versions - use get_payables_by_party for aggregation.
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                line_id,
                event_id,
                order_id,
                order_detail_id,
                supplier_timeline_version,
                obligation_type,
                party_id,
                party_name,
                amount,
                currency,
                calculation_basis,
                calculation_rate,
                calculation_description,
                ingested_at
            FROM supplier_payable_lines
            WHERE order_id = ?
            ORDER BY order_detail_id, obligation_type, party_id
        """, (order_id,))

        columns = [
            'line_id', 'event_id', 'order_id', 'order_detail_id', 'supplier_timeline_version',
            'obligation_type', 'party_id', 'party_name', 'amount', 'currency',
            'calculation_basis', 'calculation_rate', 'calculation_description', 'ingested_at'
        ]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_payables_by_party(self, order_id: str):
        """
        Get total effective payables grouped by party_id and obligation_type.

        **STATUS-DRIVEN MODEL**:
        - Baseline supplier cost determined by latest supplier_timeline.status
        - Adjustments (penalties/credits) are ALWAYS additive
        - Commission/tax are conditionally included based on supplier status

        Use get_total_effective_payables() for status-aware calculation.
        This method returns RAW aggregation (all lines summed).
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                party_id,
                party_name,
                obligation_type,
                SUM(amount) as total_amount,
                currency,
                COUNT(*) as line_count,
                MIN(ingested_at) as first_recorded,
                MAX(ingested_at) as last_updated
            FROM supplier_payable_lines
            WHERE order_id = ?
            GROUP BY party_id, party_name, obligation_type, currency
            ORDER BY party_id, obligation_type
        """, (order_id,))

        columns = [
            'party_id', 'party_name', 'obligation_type', 'total_amount', 'currency',
            'line_count', 'first_recorded', 'last_updated'
        ]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_total_effective_payables(self, order_id: str):
        """
        Get effective payables using party-level projection with amount_effect.

        NEW v2 Logic:
        1. Get baseline from latest supplier_timeline.status per order_detail
        2. Use party-level projection: latest obligation per (party_id, obligation_type)
        3. Apply amount_effect: INCREASES_PAYABLE adds, DECREASES_PAYABLE subtracts
        4. Conditionally include timeline-linked vs standalone based on status

        Status rules:
        - ISSUED/Confirmed: baseline = amount_due (with amount_basis display), include ALL obligations
        - CancelledWithFee: baseline = cancellation_fee, EXCLUDE timeline obligations (version >= 1), keep standalone (version = -1)
        - CancelledNoFee: baseline = 0, EXCLUDE timeline obligations, keep standalone
        """
        self._ensure_connected()
        cursor = self.conn.cursor()

        # Step 1: Get latest status per (order_detail_id, supplier_reference_id, fulfillment_instance_id)
        # NEW: Multi-instance support - returns multiple rows for passes (one per redemption)
        cursor.execute("""
            WITH latest_status AS (
                SELECT
                    order_id,
                    order_detail_id,
                    supplier_id,
                    supplier_reference_id,
                    fulfillment_instance_id,
                    status,
                    amount,
                    amount_basis,
                    cancellation_fee_amount,
                    currency,
                    supplier_timeline_version,
                    ROW_NUMBER() OVER (
                        PARTITION BY order_id, order_detail_id, supplier_reference_id,
                                     COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__')
                        ORDER BY supplier_timeline_version DESC
                    ) as rn
                FROM supplier_timeline
                WHERE order_id = ?
            )
            SELECT * FROM latest_status WHERE rn = 1
        """, (order_id,))

        latest_statuses = [dict(zip(
            ['order_id', 'order_detail_id', 'supplier_id', 'supplier_reference_id',
             'fulfillment_instance_id', 'status', 'amount', 'amount_basis', 'cancellation_fee_amount', 'currency',
             'supplier_timeline_version', 'rn'],
            row
        )) for row in cursor.fetchall()]

        result = []

        for status_row in latest_statuses:
            order_detail_id = status_row['order_detail_id']
            supplier_reference_id = status_row['supplier_reference_id']
            fulfillment_instance_id = status_row['fulfillment_instance_id']  # NEW: Multi-instance support
            fulfillment_instance_key = fulfillment_instance_id if fulfillment_instance_id else '__BOOKING_LEVEL__'  # For scoping
            status = status_row['status']
            amount_basis = status_row['amount_basis']

            # Calculate baseline from status
            # NEW: Cancellation fees are now in party lines, so baseline is always 0 for cancelled
            if status in ('Confirmed', 'ISSUED', 'Invoiced', 'Settled'):
                baseline_amount = status_row['amount'] or 0
                baseline_reason = f"Supplier cost (status: {status}" + (f", basis: {amount_basis}" if amount_basis else "") + ")"
                include_timeline_obligations = True
            elif status == 'CancelledWithFee':
                # NEW: Fee is in party lines (CANCELLATION_FEE obligation), baseline is 0
                # Fallback: If no CANCELLATION_FEE line exists (legacy event), use cancellation_fee_amount
                baseline_amount = 0  # Fee will come from party lines
                baseline_reason = f"Cancelled (status: {status}, fee in party lines)"
                include_timeline_obligations = False  # Exclude old timeline obligations when cancelled
            elif status in ('CancelledNoFee', 'Voided'):
                baseline_amount = 0
                baseline_reason = f"Cancelled without fee (status: {status})"
                include_timeline_obligations = False
            else:
                baseline_amount = 0
                baseline_reason = f"Unknown status: {status}"
                include_timeline_obligations = False

            # Step 2: Get party-level projection with amount_effect
            # Key insight: We need to check if the latest supplier_timeline_version has ANY payable lines
            # - If YES: use party-level projection from that version (Scenario D - adjusted affiliate)
            # - If NO: exclude all timeline obligations (Scenario B - empty parties array)

            latest_timeline_version = status_row['supplier_timeline_version']

            # Check if the latest supplier_timeline_version has any payable lines (scoped to this instance)
            cursor.execute("""
                SELECT COUNT(*) FROM supplier_payable_lines
                WHERE order_id = ? AND order_detail_id = ?
                  AND supplier_reference_id = ?
                  AND COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__') = ?
                  AND supplier_timeline_version = ?
            """, (order_id, order_detail_id, supplier_reference_id, fulfillment_instance_key, latest_timeline_version))
            has_lines_in_latest_version = cursor.fetchone()[0] > 0

            if include_timeline_obligations:
                # ISSUED/Confirmed: include ALL timeline obligations (party-level projection scoped to this instance)
                cursor.execute("""
                    WITH latest_per_party AS (
                        SELECT party_id, obligation_type, MAX(supplier_timeline_version) as latest_version
                        FROM supplier_payable_lines
                        WHERE order_id = ? AND order_detail_id = ?
                          AND supplier_reference_id = ?
                          AND COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__') = ?
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
                      AND COALESCE(p.fulfillment_instance_id, '__BOOKING_LEVEL__') = ?
                """, (order_id, order_detail_id, supplier_reference_id, fulfillment_instance_key, order_id, order_detail_id, supplier_reference_id, fulfillment_instance_key))
                timeline_obligations = [dict(zip(['obligation_type', 'party_type', 'party_id', 'party_name', 'amount', 'amount_effect', 'currency'], row))
                                       for row in cursor.fetchall()]
            else:
                # CancelledWithFee/CancelledNoFee: check if latest version has lines
                if has_lines_in_latest_version:
                    # Scenario D: Latest version has updated parties → include ONLY those (from latest version, scoped to instance)
                    cursor.execute("""
                        SELECT obligation_type, party_type, party_id, party_name, amount, amount_effect, currency
                        FROM supplier_payable_lines
                        WHERE order_id = ? AND order_detail_id = ?
                          AND supplier_reference_id = ?
                          AND COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__') = ?
                          AND supplier_timeline_version = ?
                    """, (order_id, order_detail_id, supplier_reference_id, fulfillment_instance_key, latest_timeline_version))
                    timeline_obligations = [dict(zip(['obligation_type', 'party_type', 'party_id', 'party_name', 'amount', 'amount_effect', 'currency'], row))
                                           for row in cursor.fetchall()]
                else:
                    # Scenario B: Latest version has NO lines (empty parties array) → exclude all timeline obligations
                    timeline_obligations = []

            # Get standalone adjustments (version = -1) separately - ALWAYS included (scoped to instance)
            cursor.execute("""
                SELECT obligation_type, party_type, party_id, party_name, amount, amount_effect, currency
                FROM supplier_payable_lines
                WHERE order_id = ? AND order_detail_id = ?
                  AND supplier_reference_id = ?
                  AND COALESCE(fulfillment_instance_id, '__BOOKING_LEVEL__') = ?
                  AND supplier_timeline_version = -1
            """, (order_id, order_detail_id, supplier_reference_id, fulfillment_instance_key))

            standalone_obligations = [dict(zip(['obligation_type', 'party_type', 'party_id', 'party_name', 'amount', 'amount_effect', 'currency'], row))
                                     for row in cursor.fetchall()]

            # Combine timeline + standalone
            obligations = timeline_obligations + standalone_obligations

            # Step 3: Group obligations by party and calculate party-level payables
            from collections import defaultdict
            party_groups = defaultdict(lambda: {'obligations': [], 'total_adjustment': 0})

            # Get supplier party_id from status_row
            supplier_party_id = status_row['supplier_id']

            for obl in obligations:
                party_id = obl['party_id']
                party_groups[party_id]['obligations'].append(obl)
                party_groups[party_id]['party_type'] = obl.get('party_type', 'UNKNOWN')
                party_groups[party_id]['party_name'] = obl['party_name']

                # Apply amount_effect logic per party
                if obl['amount_effect'] == 'INCREASES_PAYABLE':
                    party_groups[party_id]['total_adjustment'] += obl['amount']
                elif obl['amount_effect'] == 'DECREASES_PAYABLE':
                    party_groups[party_id]['total_adjustment'] -= obl['amount']

            # Step 4: Build party-separated payables
            parties_payables = []

            # Always include supplier party (even if no obligations)
            supplier_obligations = party_groups[supplier_party_id]['obligations'] if supplier_party_id in party_groups else []
            supplier_total_adjustment = party_groups[supplier_party_id]['total_adjustment'] if supplier_party_id in party_groups else 0

            # MIGRATION FALLBACK: If CancelledWithFee but no CANCELLATION_FEE line, use legacy field
            if status == 'CancelledWithFee' and status_row['cancellation_fee_amount']:
                has_cancellation_fee_line = any(
                    obl['obligation_type'] == 'CANCELLATION_FEE'
                    for obl in supplier_obligations
                )
                if not has_cancellation_fee_line and status_row['cancellation_fee_amount'] > 0:
                    # Legacy event - add fee as baseline (deprecated pattern)
                    baseline_amount = status_row['cancellation_fee_amount']
                    baseline_reason = f"Cancellation fee (legacy - from cancellation_fee_amount field)"

            supplier_payable = {
                'party_id': supplier_party_id,
                'party_type': 'SUPPLIER',
                'party_name': status_row['supplier_id'],  # Use supplier_id as name fallback
                'baseline': baseline_amount,
                'baseline_reason': baseline_reason,
                'obligations': supplier_obligations,
                'total_adjustment': supplier_total_adjustment,
                'total_payable': baseline_amount + supplier_total_adjustment,
                'currency': status_row['currency']
            }
            parties_payables.append(supplier_payable)

            # Add non-supplier parties (affiliates, tax authorities, etc.)
            for party_id, party_data in party_groups.items():
                if party_id != supplier_party_id:
                    party_payable = {
                        'party_id': party_id,
                        'party_type': party_data['party_type'],
                        'party_name': party_data['party_name'],
                        'baseline': 0,  # Non-supplier parties have no baseline
                        'baseline_reason': 'No baseline (non-supplier party)',
                        'obligations': party_data['obligations'],
                        'total_adjustment': party_data['total_adjustment'],
                        'total_payable': party_data['total_adjustment'],  # For non-suppliers, total = adjustment only
                        'currency': status_row['currency']
                    }
                    parties_payables.append(party_payable)

            # Step 5: Build result structure
            result.append({
                'order_detail_id': order_detail_id,
                'supplier_reference_id': supplier_reference_id,
                'fulfillment_instance_id': fulfillment_instance_id,  # NEW: Multi-instance support
                'supplier_baseline': {
                    'supplier_id': status_row['supplier_id'],
                    'amount': baseline_amount,
                    'amount_basis': amount_basis,
                    'reason': baseline_reason,
                    'status': status,
                    'currency': status_row['currency']
                },
                'parties': parties_payables,  # NEW: Party-separated payables
                'party_obligations': obligations,  # DEPRECATED: Keep for backward compatibility
                'total_payable': sum(p['total_payable'] for p in parties_payables)  # Sum across all parties
            })

        return result

    def get_payables_timeline(self, order_id: str):
        """
        Get payables in chronological order showing evolution across timeline versions.

        Useful for audit trail: see when each obligation was created (commission, penalty, etc.)
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                supplier_timeline_version,
                obligation_type,
                party_id,
                party_name,
                amount,
                currency,
                calculation_description,
                ingested_at,
                event_id,
                line_id
            FROM supplier_payable_lines
            WHERE order_id = ?
            ORDER BY supplier_timeline_version ASC, obligation_type
        """, (order_id,))

        columns = [
            'supplier_timeline_version', 'obligation_type', 'party_id', 'party_name',
            'amount', 'currency', 'calculation_description', 'ingested_at', 'event_id', 'line_id'
        ]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_supplier_payables_by_detail(self, order_detail_id: str):
        """Get supplier payable breakdown for a specific order_detail"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                line_id,
                event_id,
                order_id,
                order_detail_id,
                supplier_timeline_version,
                obligation_type,
                party_id,
                party_name,
                amount,
                currency,
                calculation_basis,
                calculation_rate,
                calculation_description,
                ingested_at
            FROM supplier_payable_lines
            WHERE order_detail_id = ?
            ORDER BY obligation_type, party_id
        """, (order_detail_id,))

        columns = [
            'line_id', 'event_id', 'order_id', 'order_detail_id', 'supplier_timeline_version',
            'obligation_type', 'party_id', 'party_name', 'amount', 'currency',
            'calculation_basis', 'calculation_rate', 'calculation_description', 'ingested_at'
        ]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_supplier_effective_payables(self, order_id: str, order_detail_id: Optional[str] = None):
        """
        Get effective supplier payables using status-driven obligation model.
        
        Logic:
        1. Get latest event per supplier instance (supplier_id + supplier_ref)
        2. Map status to effective obligation:
           - Confirmed/Invoiced/Settled → amount_due
           - CancelledWithFee → cancellation_fee_amount
           - CancelledNoFee/Voided → 0
        """
        cursor = self.conn.cursor()
        
        # Build WHERE clause
        where_clause = "WHERE order_id = ?"
        params = [order_id]
        if order_detail_id:
            where_clause += " AND order_detail_id = ?"
            params.append(order_detail_id)
        
        query = f"""
        WITH ranked AS (
          SELECT
            *,
            ROW_NUMBER() OVER (
              PARTITION BY order_id, order_detail_id, supplier_id, supplier_reference_id
              ORDER BY supplier_timeline_version DESC, emitted_at DESC
            ) AS rn
          FROM supplier_timeline
          {where_clause}
        ),
        latest_per_supplier AS (
          SELECT * FROM ranked WHERE rn = 1
        )
        SELECT
          supplier_id,
          supplier_reference_id,
          status,
          CASE
            WHEN status IN ('Confirmed', 'ISSUED', 'Invoiced', 'Settled') THEN COALESCE(amount, 0)
            WHEN status = 'CancelledWithFee' THEN COALESCE(cancellation_fee_amount, 0)
            WHEN status IN ('CancelledNoFee', 'Voided') THEN 0
            ELSE 0
          END AS effective_payable,
          currency,
          order_id,
          order_detail_id,
          supplier_timeline_version,
          event_id,
          emitted_at,
          metadata
        FROM latest_per_supplier
        ORDER BY order_detail_id, supplier_id
        """
        
        cursor.execute(query, params)
        columns = [
            'supplier_id', 'supplier_reference_id', 'status', 'effective_payable', 'currency',
            'order_id', 'order_detail_id', 'supplier_timeline_version', 'event_id', 'emitted_at', 'metadata'
        ]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_supplier_payables_with_status(self, order_id: str):
        """
        Get supplier payables with status-driven effective obligations.

        Returns breakdown per supplier instance with:
        - Latest status per supplier instance (supplier_id + supplier_ref)
        - Effective payable based on status
        - Breakdown lines (supplier cost, affiliate commission, tax)
        """
        cursor = self.conn.cursor()

        # Step 1: Get latest status per supplier instance
        query_status = """
        WITH ranked AS (
          SELECT
            order_id,
            order_detail_id,
            supplier_id,
            supplier_reference_id,
            status,
            amount,
            currency,
            cancellation_fee_amount,
            cancellation_fee_currency,
            supplier_timeline_version,
            event_id,
            emitted_at,
            metadata,
            ROW_NUMBER() OVER (
              PARTITION BY order_id, order_detail_id, supplier_id, supplier_reference_id
              ORDER BY supplier_timeline_version DESC, emitted_at DESC
            ) AS rn
          FROM supplier_timeline
          WHERE order_id = ?
        )
        SELECT * FROM ranked WHERE rn = 1
        """

        cursor.execute(query_status, (order_id,))
        status_columns = [
            'order_id', 'order_detail_id', 'supplier_id', 'supplier_reference_id', 'status',
            'amount', 'currency', 'cancellation_fee_amount', 'cancellation_fee_currency',
            'supplier_timeline_version', 'event_id', 'emitted_at', 'metadata', 'rn'
        ]
        latest_status_rows = [dict(zip(status_columns, row)) for row in cursor.fetchall()]

        # Step 2: Get payable lines for the latest version per supplier instance
        result = []
        for status_row in latest_status_rows:
            # Calculate effective payable based on status
            status = status_row['status']
            if status in ('Confirmed', 'ISSUED', 'Invoiced', 'Settled'):
                effective_payable = status_row['amount'] or 0
            elif status == 'CancelledWithFee':
                effective_payable = status_row['cancellation_fee_amount'] or 0
            elif status in ('CancelledNoFee', 'Voided'):
                effective_payable = 0
            else:
                effective_payable = 0

            # Get breakdown lines for this supplier instance's latest version
            cursor.execute("""
                SELECT
                    line_id,
                    event_id,
                    obligation_type,
                    party_id,
                    party_name,
                    amount,
                    currency,
                    calculation_basis,
                    calculation_rate,
                    calculation_description
                FROM supplier_payable_lines
                WHERE order_id = ?
                  AND order_detail_id = ?
                  AND supplier_timeline_version = ?
                ORDER BY obligation_type
            """, (
                status_row['order_id'],
                status_row['order_detail_id'],
                status_row['supplier_timeline_version']
            ))

            breakdown_columns = [
                'line_id', 'event_id', 'obligation_type', 'party_id', 'party_name',
                'amount', 'currency', 'calculation_basis', 'calculation_rate', 'calculation_description'
            ]
            breakdown_lines = [dict(zip(breakdown_columns, row)) for row in cursor.fetchall()]

            # Combine status info with breakdown
            result.append({
                'supplier_instance': {
                    'supplier_id': status_row['supplier_id'],
                    'supplier_reference_id': status_row['supplier_reference_id'],
                    'status': status,
                    'effective_payable': effective_payable,
                    'currency': status_row['currency'],
                    'order_detail_id': status_row['order_detail_id'],
                    'supplier_timeline_version': status_row['supplier_timeline_version'],
                    'emitted_at': status_row['emitted_at']
                },
                'breakdown_lines': breakdown_lines
            })

        return result

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
