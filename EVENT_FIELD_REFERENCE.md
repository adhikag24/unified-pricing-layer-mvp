# Event Field Reference - Unified Pricing Read Layer Prototype

This document provides a comprehensive reference for all event types in the UPRL prototype, including mandatory vs optional fields, valid values, and validation rules.

## Table of Contents

1. [PricingUpdatedEvent](#pricingupdatedevent)
2. [PaymentLifecycleEvent](#paymentlifecycleevent)
3. [SupplierLifecycleEvent](#supplierlifecycleevent)
4. [RefundIssuedEvent](#refundissuedevent)
5. [Nested Objects Reference](#nested-objects-reference)
6. [Enums and Valid Values](#enums-and-valid-values)

---

## PricingUpdatedEvent

Producer event emitted by verticals when pricing changes. This is the RAW producer event before Order Core normalization.

### Main Fields

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `event_id` | string | Optional | Any valid string | Unique event identifier (Order Core can generate if missing) |
| `event_type` | string | **Required** | `"PricingUpdated"` | Event type identifier |
| `schema_version` | string | **Required** | `"pricing.commerce.v1"` | Schema version |
| `order_id` | string | **Required** | Any valid string | Order identifier |
| `vertical` | string | Optional | `"accommodation"`, `"flight"`, `"train"`, `"car"`, `"ferry"`, `"bus"`, `"ttd"`, `"airport_transfer"` | Business vertical |
| `components` | array | **Required** | Array of [PricingComponent](#pricingcomponent) | Pricing components |
| `emitted_at` | string | **Required** | ISO 8601 datetime or string | Event emission timestamp |
| `emitter_service` | string | Optional | Any valid service name | Service that emitted the event |
| `customer_context` | object | Optional | [CustomerContext](#customercontext) | B2B customer/reseller context |
| `detail_context` | object | Optional | [DetailContext](#detailcontext) | **LEGACY**: Single order_detail context (backward compatibility) |
| `detail_contexts` | array | Optional | Array of [DetailContext](#detailcontext) | **NEW (Option A)**: Multiple order_detail contexts |
| `totals` | object | Optional | [Totals](#totals) | Validation totals |
| `meta` | object | Optional | Any valid JSON object | Additional metadata (trigger, reason, etc.) |
| `metadata` | object | Optional | Any valid JSON object | Backward compatibility alias for `meta` |

### Important Notes

- **Option A Implementation**: Supports BOTH `detail_context` (single, legacy) and `detail_contexts` (array, new)
- When multiple order_detail_ids exist, use `detail_contexts` array with one context per order_detail
- Each component's `order_detail_id` in dimensions should match one of the contexts
- Order Core adds enrichment fields during normalization: `pricing_snapshot_id`, `version`

### Example JSON

```json
{
  "event_id": "evt-12345",
  "event_type": "PricingUpdated",
  "schema_version": "pricing.commerce.v1",
  "order_id": "ORD-9001",
  "vertical": "accommodation",
  "components": [
    {
      "component_type": "RoomRate",
      "amount": 500000,
      "currency": "IDR",
      "dimensions": {
        "order_detail_id": "OD-001",
        "night_id": "N1"
      },
      "description": "Room rate for night 1"
    },
    {
      "component_type": "Tax",
      "amount": 55000,
      "currency": "IDR",
      "dimensions": {
        "order_detail_id": "OD-001"
      },
      "description": "VAT 11%"
    }
  ],
  "emitted_at": "2024-01-15T10:30:00Z",
  "emitter_service": "accommodation-service",
  "detail_contexts": [
    {
      "order_detail_id": "OD-001",
      "entity_context": {
        "entity_code": "TNPL"
      },
      "fx_context": {
        "payment_currency": "IDR",
        "supply_currency": "USD",
        "record_currency": "IDR",
        "gbv_currency": "USD",
        "payment_value": 555000,
        "supply_to_payment_fx_rate": 15500.0,
        "supply_to_record_fx_rate": 15500.0,
        "payment_to_gbv_fx_rate": 0.0000645,
        "source": "Treasury",
        "timestamp_fx_rate": "2024-01-15T00:00:00Z"
      }
    }
  ],
  "totals": {
    "customer_total": 555000,
    "currency": "IDR"
  }
}
```

---

## PaymentLifecycleEvent

Producer event for payment timeline (checkout, authorized, captured, refunded, settled).

### Main Fields

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `event_id` | string | Optional | Any valid string | Unique event identifier |
| `event_type` | string | **Required** | `"PaymentLifecycle"` | Event type identifier |
| `schema_version` | string | **Required** | `"payment.timeline.v1"` | Schema version |
| `order_id` | string | **Required** | Any valid string | Order identifier |
| `emitted_at` | string | **Required** | ISO 8601 datetime or string | Event emission timestamp |
| `payment` | object | **Required** | [Payment](#payment) | Nested payment details with status, amounts, instrument |
| `idempotency_key` | string | Optional | Any valid string | For exactly-once processing |
| `emitter_service` | string | Optional | Any valid service name | Default: `"payment-core"` |
| `meta` | object | Optional | Any valid JSON object | Additional metadata |
| `payment_method` | string | Optional | **DEPRECATED** | Legacy field for backward compatibility |
| `amount` | integer | Optional | **DEPRECATED** | Legacy field for backward compatibility |
| `currency` | string | Optional | **DEPRECATED** | Legacy field for backward compatibility |
| `pg_reference_id` | string | Optional | **DEPRECATED** | Legacy field for backward compatibility |
| `metadata` | object | Optional | **DEPRECATED** | Legacy field for backward compatibility |

### Important Notes

- Order Core adds enrichment field during normalization: `timeline_version`
- Modern implementations should use nested `payment` object, not legacy flat fields
- The `payment.status` field drives timeline progression

### Example JSON

```json
{
  "event_id": "evt-payment-56789",
  "event_type": "PaymentLifecycle",
  "schema_version": "payment.timeline.v1",
  "order_id": "ORD-9001",
  "emitted_at": "2024-01-15T10:35:00Z",
  "payment": {
    "status": "Captured",
    "payment_id": "pi_abc123",
    "pg_reference_id": "pg_xyz789",
    "payment_method": {
      "channel": "CC",
      "provider": "Stripe",
      "brand": "VISA"
    },
    "currency": "IDR",
    "authorized_amount": 555000,
    "authorized_at": "2024-01-15T10:32:00Z",
    "captured_amount": 555000,
    "captured_amount_total": 555000,
    "captured_at": "2024-01-15T10:35:00Z",
    "instrument": {
      "type": "CARD",
      "card": {
        "last4": "1234",
        "brand": "VISA",
        "exp_month": 12,
        "exp_year": 2025
      },
      "display_hint": "VISA ••••1234"
    }
  },
  "idempotency_key": "idem-payment-9001-captured",
  "emitter_service": "payment-core"
}
```

---

## SupplierLifecycleEvent

Producer event for supplier timeline (confirmed, issued, cancelled, invoice received).

### Main Fields

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `event_id` | string | Optional | Any valid string | Unique event identifier |
| `event_type` | string | **Required** | `"IssuanceSupplierLifecycle"` | Event type identifier |
| `schema_version` | string | **Required** | `"supplier.timeline.v1"` | Schema version |
| `order_id` | string | **Required** | Any valid string | Order identifier |
| `order_detail_id` | string | **Required** | Any valid string | Order detail identifier |
| `emitted_at` | string | **Required** | ISO 8601 datetime or string | Event emission timestamp |
| `supplier` | object | **Required** | [Supplier](#supplier) | Nested supplier details with status, amounts |
| `idempotency_key` | string | Optional | Any valid string | For exactly-once processing |
| `emitter_service` | string | Optional | Any valid service name | Service that emitted the event |
| `meta` | object | Optional | Any valid JSON object | Additional metadata |
| `supplier_id` | string | Optional | **DEPRECATED** | Legacy field for backward compatibility |
| `supplier_reference_id` | string | Optional | **DEPRECATED** | Legacy field for backward compatibility |
| `amount` | integer | Optional | **DEPRECATED** | Legacy field for backward compatibility |
| `currency` | string | Optional | **DEPRECATED** | Legacy field for backward compatibility |
| `metadata` | object | Optional | **DEPRECATED** | Legacy field for backward compatibility |

### Important Notes

- Order Core adds enrichment field during normalization: `supplier_timeline_version`
- Modern implementations should use nested `supplier` object, not legacy flat fields
- The `supplier.status` field tracks supplier order progression

### Example JSON

```json
{
  "event_id": "evt-supplier-11111",
  "event_type": "IssuanceSupplierLifecycle",
  "schema_version": "supplier.timeline.v1",
  "order_id": "ORD-9001",
  "order_detail_id": "OD-001",
  "emitted_at": "2024-01-15T11:00:00Z",
  "supplier": {
    "status": "ISSUED",
    "supplier_id": "SUPP-AGODA-001",
    "booking_code": "AGD123456",
    "supplier_ref": "conf-xyz-789",
    "amount_due": 350000,
    "currency": "IDR",
    "entity_context": {
      "entity_code": "TNPL",
      "merchant_of_record": "TNPL",
      "supplier_entity": "AGODA"
    },
    "fx_context": {
      "payment_currency": "IDR",
      "supply_currency": "USD",
      "record_currency": "IDR",
      "gbv_currency": "USD",
      "payment_value": 350000,
      "supply_to_payment_fx_rate": 15500.0,
      "supply_to_record_fx_rate": 15500.0,
      "payment_to_gbv_fx_rate": 0.0000645,
      "source": "Treasury",
      "timestamp_fx_rate": "2024-01-15T00:00:00Z"
    }
  },
  "idempotency_key": "idem-supplier-9001-OD-001-issued",
  "emitter_service": "issuance-service"
}
```

---

## RefundIssuedEvent

Producer event for refund issued with component breakdown and lineage tracking.

### Main Fields

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `event_id` | string | Optional | Any valid string | Unique event identifier (Order Core can generate if missing) |
| `event_type` | string | **Required** | `"refund.issued"` (from EventType enum) | Event type identifier |
| `schema_version` | string | **Required** | `"refund.components.v1"` | Schema version |
| `order_id` | string | **Required** | Any valid string | Order identifier |
| `refund_id` | string | **Required** | Any valid string | Refund identifier |
| `components` | array | **Required** | Array of [PricingComponent](#pricingcomponent) | Refund components with `refund_of_component_semantic_id` |
| `emitted_at` | datetime | **Required** | ISO 8601 datetime | Event emission timestamp |
| `emitter_service` | string | Optional | Any valid service name | Default: `"refund-service"` |
| `meta` | object | Optional | Any valid JSON object | Additional metadata |
| `metadata` | object | Optional | Any valid JSON object | Backward compatibility |

### Important Notes

- Order Core adds enrichment fields during normalization: `pricing_snapshot_id`, `version`
- Each refund component MUST have `refund_of_component_semantic_id` pointing to the original component
- Refund component amounts should be negative (representing money flowing back to customer)
- This is separate from `RefundLifecycleEvent` which tracks refund timeline (initiated/closed)

### Example JSON

```json
{
  "event_id": "evt-refund-22222",
  "event_type": "refund.issued",
  "schema_version": "refund.components.v1",
  "order_id": "ORD-9001",
  "refund_id": "REF-001",
  "components": [
    {
      "component_type": "BaseFare",
      "amount": -500000,
      "currency": "IDR",
      "dimensions": {
        "order_detail_id": "OD-001",
        "night_id": "N1"
      },
      "description": "Refund of room rate night 1",
      "is_refund": true,
      "refund_of_component_semantic_id": "cs-ORD-9001-OD-001-N1-RoomRate"
    },
    {
      "component_type": "Tax",
      "amount": -55000,
      "currency": "IDR",
      "dimensions": {
        "order_detail_id": "OD-001"
      },
      "description": "Refund of VAT 11%",
      "is_refund": true,
      "refund_of_component_semantic_id": "cs-ORD-9001-OD-001-Tax"
    }
  ],
  "emitted_at": "2024-01-16T14:30:00.000000",
  "emitter_service": "refund-service"
}
```

---

## Nested Objects Reference

### PricingComponent

Individual pricing component within an event.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `component_type` | string/enum | **Required** | See [ComponentType](#componenttype) | Type of component |
| `amount` | integer/float | **Required** | Any number (negative for refunds) | Amount in smallest currency unit |
| `currency` | string | **Required** | ISO 4217 currency code | Currency code (e.g., "IDR", "USD") |
| `dimensions` | object | **Required** | Key-value pairs | Component dimensions (order_detail_id, pax_id, leg_id, etc.) |
| `description` | string | Optional | Any valid string | Human-readable description |
| `is_refund` | boolean | Optional | `true` or `false` | Per-component refund flag (producer can set explicitly) |
| `meta` | object | Optional | Any valid JSON object | Component-level metadata |
| `metadata` | object | Optional | Any valid JSON object | Backward compatibility |
| `refund_of_component_semantic_id` | string | Optional | Valid semantic ID | For refund lineage tracking |

**Example:**
```json
{
  "component_type": "BaseFare",
  "amount": 1000000,
  "currency": "IDR",
  "dimensions": {
    "order_detail_id": "OD-001",
    "pax_id": "A1",
    "leg_id": "CGK-SIN"
  },
  "description": "Base fare CGK to SIN for passenger A1"
}
```

### CustomerContext

Customer/Reseller context for B2B scenarios.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `reseller_type_name` | string | Optional | e.g., `"B2B_AFFILIATE"` | Type of reseller |
| `reseller_id` | string | Optional | Any valid string | Reseller identifier |
| `reseller_name` | string | Optional | Any valid string | Reseller display name |

**Example:**
```json
{
  "reseller_type_name": "B2B_AFFILIATE",
  "reseller_id": "RESELLER-123",
  "reseller_name": "TravelCorp Indonesia"
}
```

### EntityContext

Legal entity context for multi-entity scenarios.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `entity_code` | string | Optional | e.g., `"TNPL"`, `"GTN"` | Legal entity code |
| `merchant_of_record` | string | Optional | Any valid string | Merchant of record entity |
| `supplier_entity` | string | Optional | Any valid string | Supplier legal entity |
| `customer_entity` | string | Optional | Any valid string | Customer legal entity |

**Example:**
```json
{
  "entity_code": "TNPL",
  "merchant_of_record": "TNPL",
  "supplier_entity": "AGODA",
  "customer_entity": "TNPL"
}
```

### FXContext

Foreign exchange context for multi-currency scenarios.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `timestamp_fx_rate` | string | Optional | ISO 8601 datetime | FX rate timestamp |
| `as_of` | string | Optional | ISO 8601 datetime | Alternative field name for timestamp |
| `payment_currency` | string | **Required** | ISO 4217 currency code | Currency customer pays in |
| `supply_currency` | string | **Required** | ISO 4217 currency code | Currency supplier bills in |
| `record_currency` | string | **Required** | ISO 4217 currency code | Currency for accounting records |
| `gbv_currency` | string | **Required** | ISO 4217 currency code | Currency for GBV reporting |
| `payment_value` | integer | **Required** | Any integer | Total payment amount |
| `supply_to_payment_fx_rate` | float | **Required** | Any float | Supply to payment exchange rate |
| `supply_to_record_fx_rate` | float | **Required** | Any float | Supply to record exchange rate |
| `payment_to_gbv_fx_rate` | float | **Required** | Any float | Payment to GBV exchange rate |
| `source` | string | **Required** | e.g., `"Treasury"` | Source of FX rates |

**Example:**
```json
{
  "timestamp_fx_rate": "2024-01-15T00:00:00Z",
  "payment_currency": "IDR",
  "supply_currency": "USD",
  "record_currency": "IDR",
  "gbv_currency": "USD",
  "payment_value": 555000,
  "supply_to_payment_fx_rate": 15500.0,
  "supply_to_record_fx_rate": 15500.0,
  "payment_to_gbv_fx_rate": 0.0000645,
  "source": "Treasury"
}
```

### DetailContext

Order detail level context (for Option A multi-order-detail support).

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `order_detail_id` | string | **Required** | Any valid string | Order detail identifier |
| `entity_context` | object | Optional | [EntityContext](#entitycontext) | Legal entity context for this detail |
| `fx_context` | object | Optional | [FXContext](#fxcontext) | FX context for this detail |

**Example:**
```json
{
  "order_detail_id": "OD-001",
  "entity_context": {
    "entity_code": "TNPL"
  },
  "fx_context": {
    "payment_currency": "IDR",
    "supply_currency": "USD",
    "record_currency": "IDR",
    "gbv_currency": "USD",
    "payment_value": 555000,
    "supply_to_payment_fx_rate": 15500.0,
    "supply_to_record_fx_rate": 15500.0,
    "payment_to_gbv_fx_rate": 0.0000645,
    "source": "Treasury",
    "timestamp_fx_rate": "2024-01-15T00:00:00Z"
  }
}
```

### Totals

Total amount validation.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `customer_total` | integer | **Required** | Any integer | Total customer-facing amount |
| `currency` | string | **Required** | ISO 4217 currency code | Currency code |

**Example:**
```json
{
  "customer_total": 555000,
  "currency": "IDR"
}
```

### Payment

Detailed payment information for payment lifecycle events.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `status` | string | **Required** | `"Authorized"`, `"Captured"`, `"Refunded"`, `"Settled"` | Payment status |
| `payment_id` | string | Optional | Any valid string | Payment intent ID (shown as Intent ID in UI) |
| `pg_reference_id` | string | Optional | Any valid string | Payment gateway reference (shown as PG Reference in UI) |
| `payment_method` | object | **Required** | [PaymentMethod](#paymentmethod) | Payment method details |
| `currency` | string | **Required** | ISO 4217 currency code | Currency code |
| `authorized_amount` | integer | Optional | Any integer | Amount authorized |
| `authorized_at` | string | Optional | ISO 8601 datetime | Authorization timestamp |
| `captured_amount` | integer | Optional | Any integer | Amount captured in this event |
| `captured_amount_total` | integer | Optional | Any integer | Running total of all captures |
| `captured_at` | string | Optional | ISO 8601 datetime | Capture timestamp |
| `instrument` | object | Optional | [PaymentInstrument](#paymentinstrument) | Masked instrument details |
| `bnpl_plan` | object | Optional | Any valid JSON object | For BNPL-specific data |

**Example:**
```json
{
  "status": "Captured",
  "payment_id": "pi_abc123",
  "pg_reference_id": "pg_xyz789",
  "payment_method": {
    "channel": "CC",
    "provider": "Stripe",
    "brand": "VISA"
  },
  "currency": "IDR",
  "authorized_amount": 555000,
  "authorized_at": "2024-01-15T10:32:00Z",
  "captured_amount": 555000,
  "captured_amount_total": 555000,
  "captured_at": "2024-01-15T10:35:00Z",
  "instrument": {
    "type": "CARD",
    "card": {
      "last4": "1234",
      "brand": "VISA",
      "exp_month": 12,
      "exp_year": 2025
    },
    "display_hint": "VISA ••••1234"
  }
}
```

### PaymentMethod

Payment method details.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `channel` | string | **Required** | e.g., `"AFFILIATE_DEPOSIT"`, `"CC"`, `"VA"` | Payment channel |
| `provider` | string | **Required** | e.g., `"AffiliateDeposit"`, `"Stripe"` | Payment provider |
| `brand` | string | **Required** | e.g., `"INTERNAL"`, `"VISA"`, `"BNI"` | Payment brand |

**Example:**
```json
{
  "channel": "CC",
  "provider": "Stripe",
  "brand": "VISA"
}
```

### PaymentInstrument

Masked payment instrument details. Only one of va/card/ewallet/bnpl should be populated based on type.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `type` | string | **Required** | `"VA"`, `"CARD"`, `"EWALLET"`, `"BNPL"`, `"QR"` | Instrument type |
| `va` | object | Optional | Key-value pairs | Virtual account details |
| `card` | object | Optional | Key-value pairs | Card details (last4, brand, exp_month, exp_year) |
| `ewallet` | object | Optional | Key-value pairs | E-wallet details (provider, phone_masked) |
| `bnpl` | object | Optional | Key-value pairs | BNPL details (provider, contract_id) |
| `display_hint` | string | Optional | Any valid string | Display hint (e.g., "BNI VA ••••1234") |
| `psp_ref` | string | Optional | Any valid string | Payment Service Provider reference |
| `psp_trace_id` | string | Optional | Any valid string | PSP trace/transaction ID |

**Example (Card):**
```json
{
  "type": "CARD",
  "card": {
    "last4": "1234",
    "brand": "VISA",
    "exp_month": 12,
    "exp_year": 2025
  },
  "display_hint": "VISA ••••1234"
}
```

**Example (Virtual Account):**
```json
{
  "type": "VA",
  "va": {
    "bank": "BNI",
    "account_number_masked": "8060•••••••1234"
  },
  "display_hint": "BNI VA ••••1234"
}
```

### Supplier

Detailed supplier information for supplier lifecycle events.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `status` | string | **Required** | `"ISSUED"`, `"Confirmed"`, `"CancelledNoFee"`, `"CancelledWithFee"`, etc. | Supplier order status |
| `supplier_id` | string | **Required** | Any valid string | Supplier identifier |
| `booking_code` | string | Optional | Any valid string | Supplier booking code |
| `supplier_ref` | string | Optional | Any valid string | Supplier reference ID |
| `amount_due` | integer | Optional | Any integer | Amount owed to supplier |
| `currency` | string | Optional | ISO 4217 currency code | Currency code |
| `fx_context` | object | Optional | [FXContext](#fxcontext) | FX context for supplier payment |
| `entity_context` | object | Optional | [EntityContext](#entitycontext) | Entity context for supplier |
| `affiliate` | object | Optional | [Affiliate](#affiliate) | For B2B affiliate cases |
| `cancellation` | object | Optional | [Cancellation](#cancellation) | For cancelled orders |

**Example:**
```json
{
  "status": "ISSUED",
  "supplier_id": "SUPP-AGODA-001",
  "booking_code": "AGD123456",
  "supplier_ref": "conf-xyz-789",
  "amount_due": 350000,
  "currency": "IDR",
  "entity_context": {
    "entity_code": "TNPL"
  }
}
```

### Affiliate

Affiliate-specific data for B2B resellers.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `reseller_id` | string | Optional | Any valid string | Reseller identifier |
| `reseller_name` | string | Optional | Any valid string | Reseller name |
| `partnerShareback` | object | **Required** | [AffiliateShareback](#affiliateshareback) | Commission/shareback details |
| `taxes` | array | **Required** | Array of [AffiliateTax](#affiliatetax) | Tax on shareback |
| `meta` | object | Optional | Any valid JSON object | Carry-over metadata |

### AffiliateShareback

Affiliate commission/shareback details.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `component_type` | string | Optional | Default: `"AffiliateShareback"` | Component type |
| `amount` | float | **Required** | Any decimal | Shareback amount |
| `currency` | string | **Required** | ISO 4217 currency code | Currency code |
| `rate` | float | **Required** | e.g., `0.1` for 10% | Commission rate |
| `basis` | string | **Required** | e.g., `"markup"` | Basis for calculation |

### AffiliateTax

Tax on affiliate shareback.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `type` | string | **Required** | e.g., `"VAT"` | Tax type |
| `amount` | float | **Required** | Any decimal | Tax amount |
| `currency` | string | **Required** | ISO 4217 currency code | Currency code |
| `rate` | float | **Required** | e.g., `0.11` for 11% | Tax rate |
| `basis` | string | **Required** | e.g., `"shareback"` | Basis for calculation |

### Cancellation

Cancellation details for supplier orders.

| Field | Type | Required | Valid Values | Description |
|-------|------|----------|--------------|-------------|
| `fee_amount` | integer | Optional | Any integer | Cancellation fee amount |
| `fee_currency` | string | Optional | ISO 4217 currency code | Currency code |

**Example:**
```json
{
  "fee_amount": 100000,
  "fee_currency": "IDR"
}
```

---

## Enums and Valid Values

### ComponentType

Commerce component types (not accounting GL codes).

**Valid Values:**
- `"BaseFare"` - Base fare for flights, trains, etc.
- `"RoomRate"` - Accommodation-specific base rate
- `"Tax"` - Generic tax component
- `"Subsidy"` - Subsidy/discount from supplier or platform
- `"Discount"` - Customer discount
- `"Fee"` - Additional fees
- `"Markup"` - Platform markup
- `"CancellationFee"` - Cancellation fee
- `"AmendmentFee"` - Amendment/modification fee
- `"Refund"` - Refund component
- `"Compensation"` - Customer compensation
- `"AffiliateShareback"` - B2B affiliate commission
- `"VAT"` - Value Added Tax

**Usage Notes:**
- Can accept both enum values and raw strings for flexibility
- Use specific types like `RoomRate` vs `BaseFare` to distinguish product-specific base pricing
- Refund components can use original component type with negative amount OR use `"Refund"` type

### EventType

Standard event types from producer services.

**Valid Values:**
- `"pricing.updated"` or `"PricingUpdated"` - Pricing changes
- `"payment.checkout"` - Payment checkout initiated
- `"payment.authorized"` - Payment authorized
- `"payment.captured"` - Payment captured
- `"payment.refunded"` - Payment refunded
- `"payment.settled"` - Payment settled with PSP
- `"refund.initiated"` - Refund process started
- `"refund.issued"` - Refund components issued
- `"refund.closed"` - Refund process completed
- `"supplier.order.confirmed"` - Supplier confirmed order
- `"supplier.order.issued"` - Order issued to supplier
- `"supplier.invoice.received"` - Supplier invoice received

### Payment Status

Valid payment status values (for `Payment.status` field).

**Valid Values:**
- `"Authorized"` - Payment authorized but not captured
- `"Captured"` - Payment captured/charged
- `"Refunded"` - Payment refunded
- `"Settled"` - Payment settled with PSP

### Supplier Status

Valid supplier status values (for `Supplier.status` field).

**Valid Values:**
- `"ISSUED"` - Order issued to supplier
- `"Confirmed"` - Supplier confirmed booking
- `"CancelledNoFee"` - Cancelled without fee
- `"CancelledWithFee"` - Cancelled with fee
- Other vertical-specific statuses as needed

### Currency Codes

ISO 4217 currency codes. Common values:
- `"IDR"` - Indonesian Rupiah
- `"USD"` - US Dollar
- `"SGD"` - Singapore Dollar
- `"MYR"` - Malaysian Ringgit
- `"THB"` - Thai Baht
- `"EUR"` - Euro
- `"AUD"` - Australian Dollar

### Dimension Keys

Common dimension keys for components:

- `order_detail_id` - Order detail identifier (most common)
- `pax_id` - Passenger identifier (flights, trains)
- `leg_id` - Flight leg identifier (e.g., "CGK-SIN")
- `segment_id` - Journey segment identifier
- `night_id` - Accommodation night identifier (e.g., "N1", "N2")
- `room_id` - Room identifier for multi-room bookings

**Best Practices:**
- Always include `order_detail_id` when applicable
- Use granular dimensions for per-passenger or per-leg pricing
- Order-level components (like MDR) have empty dimensions: `{}`

---

## Validation Rules

### General Rules

1. **Required Fields**: All fields marked as "Required" must be present in the event payload
2. **Type Validation**: Pydantic enforces type validation automatically
3. **Amount Format**: Amounts should be integers representing smallest currency unit (cents/sen), except for float-specific fields like FX rates
4. **Negative Amounts**: Refund components should have negative amounts
5. **Datetime Format**: ISO 8601 format (e.g., `"2024-01-15T10:30:00Z"`)
6. **Currency Codes**: Must be valid ISO 4217 codes

### Event-Specific Rules

**PricingUpdatedEvent:**
- Must have at least one component in `components` array
- If using Option A, each component's `order_detail_id` must match one in `detail_contexts`
- `totals.customer_total` should match sum of component amounts (validation field)

**PaymentLifecycleEvent:**
- Must have nested `payment` object with valid `status`
- `captured_amount_total` should be running sum across multiple capture events
- `instrument` details must match payment method type

**SupplierLifecycleEvent:**
- Must have nested `supplier` object with valid `status`
- `order_detail_id` must be provided (supplier facts are per order_detail)

**RefundIssuedEvent:**
- All components must have `refund_of_component_semantic_id`
- Component amounts should be negative
- `is_refund` flag should be `true`

### Semantic ID Format

Component semantic IDs follow this pattern:
```
cs-{order_id}-[{refund_id}-]{dimensions in canonical order}-{component_type}
```

Examples:
- Regular: `cs-ORD-9001-OD-001-A1-CGK-SIN-BaseFare`
- Refund: `cs-ORD-9001-REF-001-OD-001-A1-CGK-SIN-BaseFare`

---

## Complete Example: Multi-Event Scenario

Here's a complete scenario showing pricing, payment, supplier, and refund events:

### 1. PricingUpdatedEvent (Initial Booking)

```json
{
  "event_id": "evt-pricing-001",
  "event_type": "PricingUpdated",
  "schema_version": "pricing.commerce.v1",
  "order_id": "ORD-9001",
  "vertical": "accommodation",
  "components": [
    {
      "component_type": "RoomRate",
      "amount": 500000,
      "currency": "IDR",
      "dimensions": {"order_detail_id": "OD-001", "night_id": "N1"}
    },
    {
      "component_type": "RoomRate",
      "amount": 500000,
      "currency": "IDR",
      "dimensions": {"order_detail_id": "OD-001", "night_id": "N2"}
    },
    {
      "component_type": "Tax",
      "amount": 110000,
      "currency": "IDR",
      "dimensions": {"order_detail_id": "OD-001"},
      "description": "VAT 11% on total room rate"
    },
    {
      "component_type": "Markup",
      "amount": 50000,
      "currency": "IDR",
      "dimensions": {},
      "description": "Platform markup"
    }
  ],
  "emitted_at": "2024-01-15T10:30:00Z",
  "emitter_service": "accommodation-service",
  "detail_contexts": [
    {
      "order_detail_id": "OD-001",
      "entity_context": {"entity_code": "TNPL"}
    }
  ],
  "totals": {
    "customer_total": 1160000,
    "currency": "IDR"
  }
}
```

### 2. PaymentLifecycleEvent (Payment Captured)

```json
{
  "event_id": "evt-payment-002",
  "event_type": "PaymentLifecycle",
  "schema_version": "payment.timeline.v1",
  "order_id": "ORD-9001",
  "emitted_at": "2024-01-15T10:35:00Z",
  "payment": {
    "status": "Captured",
    "payment_id": "pi_abc123",
    "pg_reference_id": "pg_xyz789",
    "payment_method": {
      "channel": "CC",
      "provider": "Stripe",
      "brand": "VISA"
    },
    "currency": "IDR",
    "authorized_amount": 1160000,
    "authorized_at": "2024-01-15T10:32:00Z",
    "captured_amount": 1160000,
    "captured_amount_total": 1160000,
    "captured_at": "2024-01-15T10:35:00Z",
    "instrument": {
      "type": "CARD",
      "card": {
        "last4": "1234",
        "brand": "VISA",
        "exp_month": 12,
        "exp_year": 2025
      },
      "display_hint": "VISA ••••1234"
    }
  },
  "idempotency_key": "idem-payment-9001-captured",
  "emitter_service": "payment-core"
}
```

### 3. SupplierLifecycleEvent (Issued to Supplier)

```json
{
  "event_id": "evt-supplier-003",
  "event_type": "IssuanceSupplierLifecycle",
  "schema_version": "supplier.timeline.v1",
  "order_id": "ORD-9001",
  "order_detail_id": "OD-001",
  "emitted_at": "2024-01-15T11:00:00Z",
  "supplier": {
    "status": "ISSUED",
    "supplier_id": "SUPP-AGODA-001",
    "booking_code": "AGD123456",
    "amount_due": 950000,
    "currency": "IDR"
  },
  "idempotency_key": "idem-supplier-9001-OD-001-issued",
  "emitter_service": "issuance-service"
}
```

### 4. RefundIssuedEvent (Partial Refund - 1 Night Cancelled)

```json
{
  "event_id": "evt-refund-004",
  "event_type": "refund.issued",
  "schema_version": "refund.components.v1",
  "order_id": "ORD-9001",
  "refund_id": "REF-001",
  "components": [
    {
      "component_type": "RoomRate",
      "amount": -500000,
      "currency": "IDR",
      "dimensions": {"order_detail_id": "OD-001", "night_id": "N2"},
      "description": "Refund night 2 after cancellation",
      "is_refund": true,
      "refund_of_component_semantic_id": "cs-ORD-9001-OD-001-N2-RoomRate"
    },
    {
      "component_type": "Tax",
      "amount": -55000,
      "currency": "IDR",
      "dimensions": {"order_detail_id": "OD-001"},
      "description": "Refund partial VAT",
      "is_refund": true,
      "refund_of_component_semantic_id": "cs-ORD-9001-OD-001-Tax"
    },
    {
      "component_type": "CancellationFee",
      "amount": 100000,
      "currency": "IDR",
      "dimensions": {"order_detail_id": "OD-001"},
      "description": "Cancellation fee for night 2"
    }
  ],
  "emitted_at": "2024-01-16T14:30:00.000000",
  "emitter_service": "refund-service"
}
```

---

## Tips for Using the Prototype

1. **Start with Simple Events**: Begin with basic PricingUpdatedEvent with order-level components
2. **Add Granularity**: Progress to per-order_detail and per-pax/leg/night components
3. **Test Option A**: Use `detail_contexts` array for multi-order-detail scenarios
4. **Validate Lineage**: When creating refunds, ensure `refund_of_component_semantic_id` references match existing components
5. **Use Idempotency Keys**: Always provide idempotency_key for payment and supplier events
6. **Check Totals**: Use the `totals` validation field to verify component sum matches expected total
7. **Monitor Enrichment**: After Order Core normalization, check for added fields like `pricing_snapshot_id`, `version`, etc.

---

## Need Help?

For questions or issues with the prototype:
- Check the main PRD documents in this directory
- Review example JSON in [end_to_end_evolution.html](end_to_end_evolution.html)
- Examine the database visualization in [db.html](db.html)
- Refer to event flow examples in [scope.html](scope.html)
