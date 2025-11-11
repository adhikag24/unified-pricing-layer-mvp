"""
Latest State Projection UI component
Consolidated view of order information: pricing, payment, supplier timeline, and payables
"""
import streamlit as st
import pandas as pd
import json
from datetime import datetime


def render_unified_order_view(db):
    """Render the Latest State Projection page with all order information in one view"""

    st.markdown("## 📊 Latest State Projection")
    st.markdown("Complete order overview: latest pricing, payment state, supplier timeline, refunds, and payables")

    # Get all orders
    orders = db.get_all_orders()

    if not orders:
        st.info("📭 No orders found. Go to Producer Playground to emit some events!")
        return

    # Order selector
    selected_order = st.selectbox("Select Order", orders)

    if not selected_order:
        return

    st.markdown("---")

    # Section 1: Effective Price Components
    render_price_components_section(db, selected_order)

    st.markdown("---")

    # Section 2: Payment State
    render_payment_state_section(db, selected_order)

    st.markdown("---")

    # Section 3: Payment Timeline
    render_payment_timeline_section(db, selected_order)

    st.markdown("---")

    # Section 4: Supplier Timeline
    render_supplier_timeline_section(db, selected_order)

    st.markdown("---")

    # Section 5: Refund Timeline
    render_refund_timeline_section(db, selected_order)

    st.markdown("---")

    # Section 6: Supplier Payables
    render_payables_section(db, selected_order)


def render_price_components_section(db, order_id):
    """Show effective (latest) pricing components"""

    st.markdown("### 💰 Effective Price Components")

    all_components = db.get_order_pricing_latest(order_id)

    if not all_components:
        st.warning("No pricing components found for this order")
        return

    # Separate refund components from regular components
    regular_components = [row for row in all_components if not row['is_refund']]
    refund_components = [row for row in all_components if row['is_refund']]

    if not regular_components and not refund_components:
        st.warning("No pricing components found for this order")
        return

    # Display regular components
    if regular_components:
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
                'Version': row['version']
            })
            total_amount += row['amount']

        df = pd.DataFrame(component_list)
        st.dataframe(df, use_container_width=True)

        # Show total
        currency = regular_components[0]['currency']
        st.markdown(f"**Total**: {format_currency(total_amount, currency)}")

    # Display refund components if present
    if refund_components:
        st.markdown("#### Refunds")
        refund_list = []
        total_refund_amount = 0

        for row in refund_components:
            dimensions_dict = json.loads(row['dimensions'])

            refund_list.append({
                'Component Type': row['component_type'],
                'Amount': format_currency(row['amount'], row['currency']),
                'Currency': row['currency'],
                'Dimensions': format_dimensions(dimensions_dict),
                'Description': row['description'] or '-',
                'Refund Of': row['refund_of_component_semantic_id'] or '-'
            })
            total_refund_amount += row['amount']

        df_refunds = pd.DataFrame(refund_list)
        st.dataframe(df_refunds, use_container_width=True)

        currency = refund_components[0]['currency']
        st.markdown(f"**Total Refunded**: {format_currency(total_refund_amount, currency)}")


def render_payment_state_section(db, order_id):
    """Show current payment state (latest payment timeline entry)"""

    st.markdown("### 💳 Payment State")

    cursor = db.conn.cursor()
    cursor.execute("""
        SELECT * FROM payment_timeline
        WHERE order_id = ?
        ORDER BY timeline_version DESC
        LIMIT 1
    """, (order_id,))

    latest_payment = cursor.fetchone()

    if not latest_payment:
        st.info("No payment events found for this order")
        return

    # Display payment state with visual status indicator
    status_emoji = {
        'Authorized': '🔐',
        'Captured': '✅',
        'Refunded': '↩️',
        'Failed': '❌'
    }.get(latest_payment['status'], '💳')

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Status", f"{status_emoji} {latest_payment['status']}")

    with col2:
        st.metric("Payment Method", latest_payment['payment_method'])

    with col3:
        authorized_amt = latest_payment['authorized_amount'] or 0
        st.metric("Authorized", format_currency(authorized_amt, latest_payment['currency']))

    with col4:
        captured_amt = latest_payment['captured_amount_total'] or 0
        st.metric("Captured", format_currency(captured_amt, latest_payment['currency']))

    # Additional details in expander
    with st.expander("📋 Payment Details"):
        details_data = {
            'Field': ['Timeline Version', 'Event Type', 'Payment Intent ID', 'PG Reference', 'Emitted At'],
            'Value': [
                str(latest_payment['timeline_version']),
                str(latest_payment['event_type']),
                str(latest_payment['payment_intent_id'] or '-'),
                str(latest_payment['pg_reference_id'] or '-'),
                str(format_datetime(latest_payment['emitted_at']))
            ]
        }
        df_details = pd.DataFrame(details_data)
        st.dataframe(df_details, use_container_width=True, hide_index=True)

        # Parse instrument if present
        if latest_payment['instrument_json']:
            try:
                instrument = json.loads(latest_payment['instrument_json'])
                st.markdown("**Payment Instrument**:")
                st.json(instrument)
            except:
                st.caption("Error parsing instrument JSON")


def render_supplier_timeline_section(db, order_id):
    """Show supplier timeline events"""

    st.markdown("### 🏪 Supplier Timeline")

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

        # Show latest status prominently
        latest = events[-1]
        status_colors = {
            'Confirmed': '🟢', 'ISSUED': '🟢', 'Invoiced': '🟢', 'Settled': '🟢',
            'CancelledWithFee': '🟡', 'CancelledNoFee': '⚪', 'Voided': '⚪'
        }
        badge = status_colors.get(latest['status'], '🔵')

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Latest Status", f"{badge} {latest['status'] or '-'}")
        with col2:
            st.metric("Supplier", latest['supplier_id'])
        with col3:
            if latest['amount']:
                st.metric("Amount", format_currency(latest['amount'], latest['currency'] or 'IDR'))
            else:
                st.metric("Amount", "-")

        # Timeline events table
        supplier_list = []
        for row in events:
            supplier_list.append({
                'Version': row['supplier_timeline_version'],
                'Event Type': row['event_type'],
                'Status': row['status'] or '-',
                'Booking Code': row['booking_code'] or '-',
                'Amount': format_currency(row['amount'], row['currency']) if row['amount'] else '-',
                'Emitted At': format_datetime(row['emitted_at'])
            })

        df = pd.DataFrame(supplier_list)
        st.dataframe(df, use_container_width=True)


def render_payment_timeline_section(db, order_id):
    """Show payment timeline evolution"""

    st.markdown("### 💳 Payment Timeline")

    timeline = db.get_payment_timeline(order_id)

    if not timeline:
        st.info("No payment timeline events found for this order")
        return

    # Show timeline events table
    payment_list = []
    for row in timeline:
        payment_list.append({
            'Version': row['timeline_version'],
            'Event Type': row['event_type'],
            'Status': row['status'],
            'Payment Method': row['payment_method'],
            'Authorized': format_currency(row['authorized_amount'], row['currency']) if row['authorized_amount'] else '-',
            'Captured (Total)': format_currency(row['captured_amount_total'], row['currency']) if row['captured_amount_total'] else '-',
            'Emitted At': format_datetime(row['emitted_at'])
        })

    df = pd.DataFrame(payment_list)
    st.dataframe(df, use_container_width=True)

    # Show full event details in expander
    with st.expander("📋 View Event Details"):
        for idx, row in enumerate(timeline):
            st.markdown(f"**Version {row['timeline_version']}: {row['event_type']}**")
            col1, col2 = st.columns(2)
            with col1:
                st.write(f"• Event ID: `{row['event_id']}`")
                st.write(f"• Status: {row['status']}")
                st.write(f"• Payment Method: {row['payment_method']}")
                if row['payment_intent_id']:
                    st.write(f"• Payment Intent ID: {row['payment_intent_id']}")
            with col2:
                if row['pg_reference_id']:
                    st.write(f"• PG Reference: {row['pg_reference_id']}")
                st.write(f"• Emitter: {row['emitter_service']}")
                st.write(f"• Emitted At: {format_datetime(row['emitted_at'])}")

            # Show instrument JSON if present
            if row['instrument_json']:
                try:
                    instrument = json.loads(row['instrument_json'])
                    st.json(instrument)
                except:
                    pass

            if idx < len(timeline) - 1:
                st.markdown("---")


def render_refund_timeline_section(db, order_id):
    """Show refund timeline evolution"""

    st.markdown("### ↩️ Refund Timeline")

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

    for refund_id, events in refund_groups.items():
        st.markdown(f"#### {refund_id}")

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
        refund_list = []
        for row in events:
            status_emoji = {
                'INITIATED': '🔄',
                'PROCESSING': '⏳',
                'ISSUED': '✅',
                'CLOSED': '🔒',
                'FAILED': '❌'
            }.get(row['status'], '↩️')

            refund_list.append({
                'Version': row['refund_timeline_version'],
                'Status': f"{status_emoji} {row['status']}",
                'Event Type': row['event_type'],
                'Amount': format_currency(row['refund_amount'], row['currency']),
                'Reason': row['refund_reason'] or '-',
                'Emitted At': format_datetime(row['emitted_at'])
            })

        df = pd.DataFrame(refund_list)
        st.dataframe(df, use_container_width=True)


def render_payables_section(db, order_id):
    """Show supplier payables breakdown"""

    st.markdown("### 💼 Supplier Payables")

    # Get total effective payables (v2 with party-level projection)
    payables_data = db.get_total_effective_payables(order_id)

    if not payables_data:
        st.info("No supplier payables recorded for this order")
        return

    # Display each order_detail
    grand_total_payable = 0
    currency = 'IDR'

    for detail_data in payables_data:
        order_detail_id = detail_data['order_detail_id']
        supplier_baseline = detail_data['supplier_baseline']
        parties = detail_data.get('parties', [])
        total_payable = detail_data['total_payable']

        # Status badge
        status_colors = {
            'Confirmed': '🟢', 'ISSUED': '🟢', 'Invoiced': '🟢', 'Settled': '🟢',
            'CancelledWithFee': '🟡', 'CancelledNoFee': '⚪', 'Voided': '⚪'
        }
        status = supplier_baseline['status']
        badge = status_colors.get(status, '🔵')

        # Header
        st.markdown(f"#### Order Detail: {order_detail_id}")
        st.caption(f"Status: {badge} **{status}** | Supplier: **{supplier_baseline['supplier_id']}**")

        currency = supplier_baseline['currency'] or 'IDR'

        # Display party-separated payables
        if parties:
            for party in parties:
                party_type = party.get('party_type', 'UNKNOWN')
                party_type_badge = {
                    'SUPPLIER': '🏪',
                    'AFFILIATE': '🤝',
                    'TAX_AUTHORITY': '🏛️'
                }.get(party_type, '❓')

                # Party metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    baseline_amt = party['baseline']
                    if party_type == 'SUPPLIER':
                        amount_basis = supplier_baseline.get('amount_basis')
                        basis_label = f" ({amount_basis})" if amount_basis else ""
                        st.metric(f"{party_type_badge} {party['party_name']} - Baseline{basis_label}",
                                 format_currency(baseline_amt, currency))
                    else:
                        st.metric(f"{party_type_badge} {party['party_name']} - Baseline",
                                 format_currency(baseline_amt, currency))
                with col2:
                    adjustment = party['total_adjustment']
                    st.metric("Adjustments (Net)", format_currency(adjustment, currency), delta=adjustment)
                with col3:
                    party_total = party['total_payable']
                    st.metric("Total Payable", format_currency(party_total, currency))

                # Show obligations in expander
                if party['obligations']:
                    with st.expander(f"View {len(party['obligations'])} Obligation(s)"):
                        for obl in party['obligations']:
                            effect_color = "🔺" if obl['amount_effect'] == 'INCREASES_PAYABLE' else "🔻"
                            effect_text = "INCREASES" if obl['amount_effect'] == 'INCREASES_PAYABLE' else "DECREASES"

                            st.markdown(f"**{effect_color} {obl['obligation_type']}** ({effect_text} PAYABLE)")
                            st.write(f"• Amount: {format_currency(obl['amount'], obl['currency'])}")
                            if obl.get('calculation_description'):
                                st.caption(f"  💡 {obl['calculation_description']}")
                            st.markdown("---")
        else:
            st.caption("ℹ️ No party payables (legacy format)")

        grand_total_payable += total_payable
        st.markdown("---")

    # Grand total
    st.markdown(f"### **Grand Total Payable: {format_currency(grand_total_payable, currency)}**")


# Utility functions

def format_currency(amount, currency):
    """Format currency amount with proper decimal handling per currency"""
    # Zero-decimal currencies (no subdivision in practice)
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
