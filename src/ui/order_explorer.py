"""
Order Explorer UI component
Browse order pricing breakdowns, timelines, and component lineage
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime


def render_order_explorer(db):
    """Render the Order Explorer page"""

    st.markdown("## 🔍 Order Explorer")
    st.markdown("Browse pricing breakdowns, payment timelines, and component lineage")

    # Get all orders
    orders = db.get_all_orders()

    if not orders:
        st.info("📭 No orders found. Go to Producer Playground to emit some events!")
        return

    # Order selector
    selected_order = st.selectbox("Select Order", orders)

    if not selected_order:
        return

    # Tabs for different views
    tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
        "💰 Latest Breakdown",
        "📜 Version History",
        "🔗 Component Lineage",
        "💳 Payment Timeline",
        "🏪 Supplier Timeline",
        "↩️ Refund Timeline",
        "💼 Supplier Payables"
    ])

    with tab1:
        refund_components = render_latest_breakdown(db, selected_order)
        # Render refunds separately if they exist
        if refund_components:
            st.markdown("---")  # Visual separator
            render_refunds(refund_components)

    with tab2:
        render_version_history(db, selected_order)

    with tab3:
        render_component_lineage(db, selected_order)

    with tab4:
        render_payment_timeline(db, selected_order)

    with tab5:
        render_supplier_timeline(db, selected_order)

    with tab6:
        render_refund_timeline_tab(db, selected_order)

    with tab7:
        render_supplier_payables(db, selected_order)


def render_latest_breakdown(db, order_id):
    """Show latest pricing breakdown (excluding refunds)"""

    st.markdown("### Current Pricing Breakdown")

    all_components = db.get_order_pricing_latest(order_id)

    if not all_components:
        st.warning("No pricing components found for this order")
        return

    # Separate refund components from regular components
    regular_components = [row for row in all_components if not row['is_refund']]
    refund_components = [row for row in all_components if row['is_refund']]

    if not regular_components:
        st.warning("No regular pricing components found for this order")
        # Return refund components even if no regular components exist
        return refund_components

    # Convert to DataFrame for display
    component_list = []
    total_amount = 0

    for row in regular_components:
        dimensions_dict = json.loads(row['dimensions'])

        component_list.append({
            'Component Type': row['component_type'],
            'Amount': format_currency(row['amount'], row['currency']),
            'Currency': row['currency'],
            'Dimensions': format_dimensions(dimensions_dict),
            'Description': row['description'] or '-',
            'Semantic ID': row['component_semantic_id'],
            'Version': row['version']
        })
        total_amount += row['amount']

    df = pd.DataFrame(component_list)

    # Display components
    st.dataframe(df, use_container_width=True)

    # Show total
    currency = regular_components[0]['currency']
    st.markdown(f"### Total: **{format_currency(total_amount, currency)}**")

    # Show metadata
    with st.expander("📋 Metadata"):
        latest_component = regular_components[0]
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Version", latest_component['version'])
        with col2:
            st.metric("Components", len(regular_components))
        with col3:
            st.metric("Emitter", latest_component['emitter_service'])

        st.text(f"Pricing Snapshot ID: {latest_component['pricing_snapshot_id']}")
        st.text(f"Emitted At: {latest_component['emitted_at']}")
        st.text(f"Ingested At: {latest_component['ingested_at']}")

    # Return refund components for rendering separately
    return refund_components


def render_refunds(refund_components):
    """Show refund components separately with lineage information"""

    if not refund_components:
        return  # No refunds to display

    st.markdown("### Refunds")
    st.info("💡 Refunds are shown separately from the current pricing breakdown. They reverse original components.")

    # Convert to DataFrame for display
    refund_list = []
    total_refund_amount = 0

    for row in refund_components:
        dimensions_dict = json.loads(row['dimensions'])

        # Show which component this refund reverses
        refund_of_display = row['refund_of_component_semantic_id'] or '-'

        refund_list.append({
            'Component Type': row['component_type'],
            'Amount': format_currency(row['amount'], row['currency']),
            'Currency': row['currency'],
            'Dimensions': format_dimensions(dimensions_dict),
            'Description': row['description'] or '-',
            'Semantic ID': row['component_semantic_id'],
            'Refund Of': refund_of_display,
            'Version': row['version']
        })
        total_refund_amount += row['amount']

    df = pd.DataFrame(refund_list)

    # Display refund components
    st.dataframe(df, use_container_width=True)

    # Show total refund amount
    currency = refund_components[0]['currency']
    st.markdown(f"### Total Refunded: **{format_currency(total_refund_amount, currency)}**")


def render_version_history(db, order_id):
    """Show all pricing versions for an order"""

    st.markdown("### Version History")

    history = db.get_order_pricing_history(order_id)

    if not history:
        st.warning("No version history found")
        return

    # Convert to DataFrame
    history_list = []
    for row in history:
        history_list.append({
            'Version': row['version'],
            'Snapshot ID': row['pricing_snapshot_id'][:16] + '...',
            'Components': row['component_count'],
            'Total Amount': format_currency(row['total_amount'], row['currency']),
            'Currency': row['currency'],
            'Emitted At': format_datetime(row['emitted_at'])
        })

    df = pd.DataFrame(history_list)
    st.dataframe(df, use_container_width=True)

    # Detail view for selected version
    selected_version = st.selectbox("Select version to view details", [h['Version'] for h in history_list])

    if selected_version:
        st.markdown(f"#### Version {selected_version} - Component Details")

        cursor = db.conn.cursor()
        cursor.execute("""
            SELECT * FROM pricing_components_fact
            WHERE order_id = ? AND version = ?
            ORDER BY component_type, dimensions
        """, (order_id, selected_version))

        components = cursor.fetchall()

        component_details = []
        for row in components:
            dimensions_dict = json.loads(row['dimensions'])

            # Show full semantic ID for refund_of (precise reference)
            refund_of_display = row['refund_of_component_semantic_id'] or '-'

            component_details.append({
                'Type': row['component_type'],
                'Amount': format_currency(row['amount'], row['currency']),
                'Dimensions': format_dimensions(dimensions_dict),
                'Description': row['description'] or '-',
                'Semantic ID': row['component_semantic_id'],
                'Refund Of': refund_of_display
            })

        df_details = pd.DataFrame(component_details)
        st.dataframe(df_details, use_container_width=True)


def render_component_lineage(db, order_id):
    """Show component lineage including refunds"""

    st.markdown("### Component Lineage")
    st.markdown("Trace component history and refund relationships")

    # Get only non-refund semantic IDs for this order
    # Refunds have different semantic IDs but are shown via refund_of_component_semantic_id
    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT DISTINCT component_semantic_id
        FROM pricing_components_fact
        WHERE order_id = ? AND is_refund = 0
        ORDER BY component_semantic_id
    """, (order_id,))

    semantic_ids = [row[0] for row in cursor.fetchall()]

    if not semantic_ids:
        st.warning("No components found")
        return

    selected_semantic_id = st.selectbox("Select Component", semantic_ids)

    if selected_semantic_id:
        lineage = db.get_component_lineage(selected_semantic_id)

        # Original component occurrences
        st.markdown("#### Original Component Occurrences")

        if lineage['original']:
            original_list = []
            for row in lineage['original']:
                dimensions_dict = json.loads(row['dimensions'])
                original_list.append({
                    'Version': row['version'],
                    'Amount': format_currency(row['amount'], row['currency']),
                    'Dimensions': format_dimensions(dimensions_dict),
                    'Description': row['description'] or '-',
                    'Instance ID': row['component_instance_id'],
                    'Emitted At': format_datetime(row['emitted_at'])
                })

            df_original = pd.DataFrame(original_list)
            st.dataframe(df_original, use_container_width=True)
        else:
            st.info("No original occurrences found")

        # Refund components
        st.markdown("#### Refund Components")

        if lineage['refunds']:
            refund_list = []
            for row in lineage['refunds']:
                dimensions_dict = json.loads(row['dimensions'])
                refund_list.append({
                    'Version': row['version'],
                    'Type': row['component_type'],
                    'Amount': format_currency(row['amount'], row['currency']),
                    'Dimensions': format_dimensions(dimensions_dict),
                    'Description': row['description'] or '-',
                    'Emitted At': format_datetime(row['emitted_at'])
                })

            df_refunds = pd.DataFrame(refund_list)
            st.dataframe(df_refunds, use_container_width=True)

            # Calculate net amount
            # FIX: Use only LATEST version of original component (not sum of all versions)
            latest_original = max(lineage['original'], key=lambda x: x['version']) if lineage['original'] else None
            original_amount = latest_original['amount'] if latest_original else 0

            # FIX: Group refunds by refund_id and take only latest version of each refund
            # Refund semantic IDs have format: cs-{order_id}-{refund_id}-{dimensions}-{component_type}
            # We need to extract refund_id and group by it
            refund_by_id = {}
            for row in lineage['refunds']:
                # Extract refund_id from semantic ID
                # Format: cs-ORD-XXX-RFD-XXX-... (refund_id is between second and third dash after order_id)
                semantic_id = row['component_semantic_id']
                parts = semantic_id.split('-')
                # Find RFD- pattern which indicates refund_id
                refund_id = None
                for i in range(len(parts) - 1):
                    if parts[i] == 'RFD':
                        refund_id = f"{parts[i]}-{parts[i+1]}"
                        break

                if refund_id:
                    if refund_id not in refund_by_id:
                        refund_by_id[refund_id] = []
                    refund_by_id[refund_id].append(row)

            # For each refund_id group, take only the latest version
            refund_amount = 0
            for refund_id, refund_versions in refund_by_id.items():
                latest_refund = max(refund_versions, key=lambda x: x['version'])
                refund_amount += latest_refund['amount']

            net_amount = original_amount + refund_amount

            currency = lineage['original'][0]['currency'] if lineage['original'] else 'IDR'

            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Original", format_currency(original_amount, currency))
            with col2:
                st.metric("Refunds", format_currency(refund_amount, currency))
            with col3:
                st.metric("Net", format_currency(net_amount, currency))
        else:
            st.info("No refunds for this component")


def render_payment_timeline(db, order_id):
    """Show payment timeline for order with enhanced payment lifecycle data"""

    st.markdown("### Payment Timeline")

    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT * FROM payment_timeline
        WHERE order_id = ?
        ORDER BY timeline_version ASC
    """, (order_id,))

    payments = cursor.fetchall()

    if not payments:
        st.info("No payment events found for this order")
        return

    payment_list = []
    for row in payments:
        # Parse instrument if present
        instrument_display = '-'
        if row['instrument_json']:
            try:
                instrument = json.loads(row['instrument_json'])
                instrument_display = instrument.get('display_hint', 'Internal')
            except:
                instrument_display = 'Error parsing'

        payment_list.append({
            'Version': row['timeline_version'],
            'Status': row['status'],
            'Event Type': row['event_type'],
            'Payment Method': row['payment_method'],
            'Authorized': format_currency(row['authorized_amount'] or 0, row['currency']),
            'Captured': format_currency(row['captured_amount_total'] or 0, row['currency']),
            'Instrument': instrument_display,
            'Intent ID': row['payment_intent_id'] or '-',
            'PG Reference': row['pg_reference_id'] or '-',
            'Emitted At': format_datetime(row['emitted_at'])
        })

    df = pd.DataFrame(payment_list)
    st.dataframe(df, use_container_width=True)

    # Latest status with enhanced info
    latest = payments[-1]
    status_emoji = {
        'Authorized': '🔐',
        'Captured': '✅',
        'Refunded': '↩️',
        'Failed': '❌'
    }.get(latest['status'], '💳')

    st.markdown(f"**Latest Status**: {status_emoji} `{latest['status']}` (v{latest['timeline_version']})")

    # Show payment flow summary
    if len(payments) > 1:
        with st.expander("📊 Payment Flow Summary"):
            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric("Total Events", len(payments))

            with col2:
                authorized_amt = latest['authorized_amount'] or 0
                st.metric("Authorized Amount", format_currency(authorized_amt, latest['currency']))

            with col3:
                captured_amt = latest['captured_amount_total'] or 0
                st.metric("Captured Total", format_currency(captured_amt, latest['currency']))

            # Payment intent consistency check
            intent_ids = set(p['payment_intent_id'] for p in payments if p['payment_intent_id'])
            if intent_ids:
                st.caption(f"Payment Intent ID: `{list(intent_ids)[0] if len(intent_ids) == 1 else 'Multiple'}`")
                if len(intent_ids) > 1:
                    st.warning(f"⚠️ Multiple payment intents detected: {', '.join(intent_ids)}")


def render_supplier_timeline(db, order_id):
    """Show supplier timeline for order"""

    st.markdown("### Supplier Timeline")

    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT * FROM supplier_timeline
        WHERE order_id = ?
        ORDER BY order_detail_id, supplier_timeline_version ASC
    """, (order_id,))

    suppliers = cursor.fetchall()

    if not suppliers:
        st.info("No supplier events found for this order")
        return

    # Group by order_detail_id
    order_details = {}
    for row in suppliers:
        od_id = row['order_detail_id']
        if od_id not in order_details:
            order_details[od_id] = []
        order_details[od_id].append(row)

    for od_id, events in order_details.items():
        st.markdown(f"#### {od_id}")

        supplier_list = []
        for row in events:
            supplier_list.append({
                'Version': row['supplier_timeline_version'],
                'Event Type': row['event_type'],
                'Supplier': row['supplier_id'],
                'Status': row['status'] or '-',
                'Booking Code': row['booking_code'] or '-',
                'Reference': row['supplier_reference_id'] or '-',
                'Amount': format_currency(row['amount'], row['currency']) if row['amount'] else '-',
                'Emitted At': format_datetime(row['emitted_at'])
            })

        df = pd.DataFrame(supplier_list)
        st.dataframe(df, use_container_width=True)

        # Latest status
        latest = events[-1]
        st.markdown(f"**Latest Status**: `{latest['event_type']}` (v{latest['supplier_timeline_version']})")


def _render_party_payables(parties, supplier_baseline, currency):
    """Helper to render party payables with obligations breakdown"""
    if not parties:
        st.caption("ℹ️ No party payables (legacy format)")
        return

    for party in parties:
        party_type = party.get('party_type', 'UNKNOWN')
        party_type_badge = {
            'SUPPLIER': '🏪',
            'AFFILIATE': '🤝',
            'TAX_AUTHORITY': '🏛️',
            'INTERNAL': '🏢'
        }.get(party_type, '❓')

        # Party header with compact display
        st.markdown(f"**{party_type_badge} {party['party_name']}** `{party_type}`")

        # Show quick summary
        party_total = party['total_payable']
        baseline_amt = party['baseline']
        adjustment = party['total_adjustment']

        if party_type == 'SUPPLIER':
            amount_basis = supplier_baseline.get('amount_basis')
            basis_note = f" (basis: {amount_basis})" if amount_basis else ""
            st.caption(f"└─ Baseline: {format_currency(baseline_amt, currency)}{basis_note} | Adjustments: {format_currency(adjustment, currency)} | **Total: {format_currency(party_total, currency)}**")
        else:
            st.caption(f"└─ Amount: {format_currency(party_total, currency)}")

        # Detailed breakdown in expander
        if party['obligations']:
            with st.expander(f"📋 View {len(party['obligations'])} Obligation(s)"):
                for obl in party['obligations']:
                    # Color code by amount_effect
                    if obl['amount_effect'] == 'INCREASES_PAYABLE':
                        effect_color = "🔺"
                        effect_text = "INCREASES"
                    elif obl['amount_effect'] == 'DECREASES_PAYABLE':
                        effect_color = "🔻"
                        effect_text = "DECREASES"
                    else:
                        effect_color = "💰"
                        effect_text = "COST"

                    st.markdown(f"**{effect_color} {obl['obligation_type']}** ({effect_text})")
                    st.write(f"• Amount: {format_currency(obl['amount'], obl['currency'])}")
                    if obl.get('calculation_description'):
                        st.caption(f"  💡 {obl['calculation_description']}")
                    st.markdown("---")


def render_supplier_payables(db, order_id):
    """Show supplier payable breakdown for order using party-level projection with amount_effect

    NEW: Supports multi-instance payables (e.g., passes with multiple redemptions)
    """

    st.markdown("### 💼 Supplier Payable Breakdown")
    st.caption("🆕 Multi-instance support: Tracks payables per fulfillment (redemptions, journeys, legs, etc.)")

    # Get total effective payables (v2 with party-level projection + multi-instance)
    payables_data = db.get_total_effective_payables(order_id)

    if not payables_data:
        st.info("No supplier payables recorded for this order")
        return

    # Group by order_detail_id
    from collections import defaultdict
    detail_groups = defaultdict(list)
    for item in payables_data:
        detail_groups[item['order_detail_id']].append(item)

    grand_total_payable = 0
    currency = 'IDR'

    for order_detail_id, instances in detail_groups.items():
        # Check if this is multi-instance:
        # - Multiple fulfillment_instance_id values (passes redemptions, train legs, etc.)
        # - Multiple supplier_reference_id values (rebooking scenario)
        has_multi_instance = (
            any(inst['fulfillment_instance_id'] is not None for inst in instances) or
            len(set(inst['supplier_reference_id'] for inst in instances)) > 1
        )

        # Get currency from first instance
        first_instance = instances[0]
        currency = first_instance['supplier_baseline']['currency'] or 'IDR'

        # Header
        st.markdown(f"### 📦 Order Detail: `{order_detail_id}`")

        # Calculate detail-level total
        detail_total = sum(inst['total_payable'] for inst in instances)

        if has_multi_instance:
            # Multi-instance display (e.g., passes redemptions, supplier rebooking)
            instance_type = "fulfillment" if any(inst['fulfillment_instance_id'] is not None for inst in instances) else "supplier"
            st.markdown(f"**Multi-Instance ({instance_type.title()})** ({len(instances)} instances)")
            st.markdown("---")

            for idx, instance_data in enumerate(instances, 1):
                fulfillment_id = instance_data['fulfillment_instance_id']
                supplier_ref = instance_data.get('supplier_reference_id', 'N/A')
                supplier_baseline = instance_data['supplier_baseline']
                parties = instance_data.get('parties', [])
                total_payable = instance_data['total_payable']
                status = supplier_baseline['status']

                # Instance badge and label
                if fulfillment_id is None:
                    # Supplier rebooking or booking-level
                    instance_badge = "🏪"
                    instance_label = f"Supplier: **{supplier_baseline['supplier_id']}** | Booking: `{supplier_ref}`"
                else:
                    # Fulfillment-level (passes redemption, train leg, etc.)
                    instance_badge = "🎟️"
                    instance_label = f"Fulfillment: `{fulfillment_id}` | Supplier: **{supplier_baseline['supplier_id']}**"

                # Status badge
                status_colors = {
                    'Confirmed': '🟢', 'ISSUED': '🟢', 'Invoiced': '🟢', 'Settled': '🟢',
                    'CancelledWithFee': '🟡', 'CancelledNoFee': '⚪', 'Voided': '⚪'
                }
                badge = status_colors.get(status, '🔵')

                st.markdown(f"#### {instance_badge} {instance_label}")
                st.caption(f"Status: {badge} **{status}** | Total Payable: **{format_currency(total_payable, currency)}**")

                # Show parties for this instance
                _render_party_payables(parties, supplier_baseline, currency)

                if idx < len(instances):
                    st.markdown("---")

            # Instance summary
            st.markdown("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown(f"**Total Payable (All {len(instances)} Instances):**")
            with col2:
                st.markdown(f"**{format_currency(detail_total, currency)}**")
        else:
            # Single instance display (traditional model)
            detail_data = instances[0]
            supplier_baseline = detail_data['supplier_baseline']
            parties = detail_data.get('parties', [])
            total_payable = detail_data['total_payable']
            status = supplier_baseline['status']

            status_colors = {
                'Confirmed': '🟢', 'ISSUED': '🟢', 'Invoiced': '🟢', 'Settled': '🟢',
                'CancelledWithFee': '🟡', 'CancelledNoFee': '⚪', 'Voided': '⚪'
            }
            badge = status_colors.get(status, '🔵')
            st.caption(f"Status: {badge} **{status}** | Total Payable: **{format_currency(total_payable, currency)}**")

            # Show parties
            _render_party_payables(parties, supplier_baseline, currency)

        grand_total_payable += detail_total
        st.markdown("---")

    # Grand total
    st.markdown(f"### Grand Total Payable: **{format_currency(grand_total_payable, currency)}**")

    # Status legend
    with st.expander("📖 v2 Model: Party-Level Projection with Amount Effect"):
        st.markdown("""
        **Status-Driven Baseline + Party-Level Projection:**

        | Status | Badge | Baseline | Party Obligations Included |
        |--------|-------|----------|---------------------------|
        | Confirmed, ISSUED, Invoiced, Settled | 🟢 | `amount_due` (with amount_basis) | ALL (timeline + standalone) |
        | CancelledWithFee | 🟡 | 0 (fee in party lines) | Latest version only (includes `CANCELLATION_FEE` line) |
        | CancelledNoFee, Voided | ⚪ | 0 | ONLY standalone (version = -1) |

        **Note**: Cancellation fees are now tracked as regular payable lines with `obligation_type='CANCELLATION_FEE'` and `amount_effect='INCREASES_PAYABLE'`.

        **Amount Effect Directionality:**
        - 🔺 **INCREASES_PAYABLE**: We owe more (e.g., affiliate commission, tax, penalty)
        - 🔻 **DECREASES_PAYABLE**: We owe less (e.g., supplier commission retention)

        **Party-Level Projection Logic:**
        1. Get latest supplier status per order_detail
        2. Query latest obligation per (party_id, obligation_type) across timeline versions
        3. Apply amount_effect: INCREASES += amount, DECREASES -= amount
        4. If cancelled: exclude timeline-linked obligations (version >= 1), keep standalone (version = -1)

        **Projection Carry-Forward:**
        - Empty parties array → obligations from v1 carried forward via projection
        - Updated parties array → latest wins (replaces previous obligations)
        """)


def render_refund_timeline_tab(db, order_id):
    """Show refund timeline evolution"""

    st.markdown("### ↩️ Refund Timeline")
    st.caption("Track refund lifecycle events: initiated, issued, closed")

    refunds = db.get_refund_timeline(order_id)

    if not refunds:
        st.info("No refund events found for this order")
        return

    # Group by refund_id
    refund_groups = {}
    for row in refunds:
        refund_id = row['refund_id']
        if refund_id not in refund_groups:
            refund_groups[refund_id] = []
        refund_groups[refund_id].append(row)

    # Show each refund as a separate section
    for refund_id, events in refund_groups.items():
        with st.expander(f"**{refund_id}** ({len(events)} events)", expanded=True):
            # Show latest status prominently
            latest = events[-1]

            # Status emoji based on status field
            status_emoji = {
                'INITIATED': '🔄',
                'PROCESSING': '⏳',
                'ISSUED': '✅',
                'CLOSED': '🔒',
                'FAILED': '❌'
            }.get(latest['status'], '↩️')

            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Status", f"{status_emoji} {latest['status']}")
            with col2:
                st.metric("Version", latest['refund_timeline_version'])
            with col3:
                st.metric("Event Type", latest['event_type'])
            with col4:
                st.metric("Refund Amount", format_currency(latest['refund_amount'], latest['currency']))

            if latest['refund_reason']:
                st.info(f"💡 **Reason**: {latest['refund_reason']}")

            # Timeline events table
            st.markdown("**Event Timeline:**")
            refund_list = []
            for row in events:
                status_emoji_row = {
                    'INITIATED': '🔄',
                    'PROCESSING': '⏳',
                    'ISSUED': '✅',
                    'CLOSED': '🔒',
                    'FAILED': '❌'
                }.get(row['status'], '↩️')

                refund_list.append({
                    'Version': row['refund_timeline_version'],
                    'Status': f"{status_emoji_row} {row['status']}",
                    'Event Type': row['event_type'],
                    'Amount': format_currency(row['refund_amount'], row['currency']),
                    'Reason': row['refund_reason'] or '-',
                    'Emitter': row['emitter_service'],
                    'Emitted At': format_datetime(row['emitted_at'])
                })

            df = pd.DataFrame(refund_list)
            st.dataframe(df, use_container_width=True)


# Utility functions

def format_currency(amount, currency):
    """Format currency amount with proper decimal handling per currency"""
    # Zero-decimal currencies (no subdivision in practice)
    # These currencies' smallest unit is the main unit itself
    ZERO_DECIMAL_CURRENCIES = ['IDR', 'JPY', 'KRW', 'VND', 'CLP', 'PYG', 'UGX', 'XAF', 'XOF']

    if currency in ZERO_DECIMAL_CURRENCIES:
        # Amount is already in main units (e.g., 246281 = IDR 246,281)
        return f"{currency} {amount:,.0f}"
    else:
        # Two-decimal currencies (has cents/pence/centimes)
        # Amount is in minor units (e.g., 150000 = USD 1,500.00)
        main_unit = amount / 100
        return f"{currency} {main_unit:,.2f}"


def format_dimensions(dimensions):
    """Format dimensions dict"""
    if not dimensions:
        return "ORDER"
    return ", ".join([f"{k}={v}" for k, v in dimensions.items()])


def format_datetime(dt_string):
    """Format datetime string"""
    try:
        dt = datetime.fromisoformat(dt_string.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return dt_string
