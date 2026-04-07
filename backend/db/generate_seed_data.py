"""
Seed Data Generator

Generates coherent CSV seed data files for populating the database.
Creates connected customers, products, suppliers, partners, orders,
conversation/messaging records, and approval workflow records.

Usage:
    uv run python backend/db/generate_seed_data.py
"""

import csv
import json
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).parent.parent / "data" / "seed"
OWNER_ID = "4c116430-f683-4a8a-91f7-546fa8bc5d76"
REFERENCE_DATE = date(2026, 4, 1)
RNG = random.Random(20260403)


def seed_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "seed-data:" + ":".join(parts)))


PRODUCT_NAMES = [
    (
        "Wireless Mouse",
        "Electronics",
        "Ergonomic wireless mouse with 2.4GHz connectivity and long battery life",
        Decimal("26.90"),
    ),
    (
        "Mechanical Keyboard",
        "Electronics",
        "RGB backlit mechanical keyboard with tactile mechanical switches",
        Decimal("64.50"),
    ),
    (
        "USB-C Hub",
        "Electronics",
        "7-in-1 USB-C hub with HDMI, USB 3.0, and SD card reader",
        Decimal("18.80"),
    ),
    (
        "Laptop Stand",
        "Accessories",
        "Adjustable aluminum laptop stand for ergonomic viewing",
        Decimal("21.40"),
    ),
    (
        "Phone Case",
        "Accessories",
        "Shockproof silicone phone case with raised edges",
        Decimal("9.75"),
    ),
    (
        "Screen Protector",
        "Accessories",
        "Tempered glass screen protector with 9H hardness",
        Decimal("6.20"),
    ),
    (
        "Webcam",
        "Electronics",
        "1080p HD webcam with autofocus and dual microphone",
        Decimal("34.80"),
    ),
    (
        "Headphones",
        "Electronics",
        "Noise-cancelling over-ear wireless headphones",
        Decimal("42.10"),
    ),
    (
        "Power Bank",
        "Electronics",
        "20000mAh portable power bank with fast charging",
        Decimal("17.60"),
    ),
    (
        "Cable Organizer",
        "Accessories",
        "Desktop cable management box with multiple slots",
        Decimal("8.50"),
    ),
]

CUSTOMER_NAMES = [
    (
        "Alice Chen",
        "alice@techcorp.com",
        "+1-555-0101",
        "TechCorp Inc",
        "Prefers expedited shipping for electronics refreshes",
        ["Electronics"],
        ["website", "email"],
        (2, 5),
    ),
    (
        "Bob Martinez",
        "bob@retailco.com",
        "+1-555-0102",
        "RetailCo LLC",
        "Bulk orders only, net-30 terms",
        ["Accessories", "Electronics"],
        ["email", "phone"],
        (8, 16),
    ),
    (
        "Carol White",
        "carol@designstudio.com",
        "+1-555-0103",
        "Design Studio",
        "Needs branded packaging for accessories",
        ["Accessories"],
        ["email", "website"],
        (3, 8),
    ),
    (
        "David Kim",
        "david@startup.io",
        "+1-555-0104",
        "Startup.io",
        "Price-sensitive and flexible on delivery windows",
        ["Electronics"],
        ["website", "phone"],
        (1, 4),
    ),
    (
        "Emma Brown",
        "emma@enterprise.com",
        "+1-555-0105",
        "Enterprise Solutions",
        "Requires invoice before shipment and quarterly reporting",
        ["Electronics", "Accessories"],
        ["email"],
        (4, 10),
    ),
]

SUPPLIER_NAMES = [
    (
        "Global Electronics Supply",
        "sales@globalsupply.com",
        "+86-21-5555-0001",
        "Electronics",
        "Primary offshore supplier for electronics SKUs",
        ["Wireless Mouse", "Mechanical Keyboard", "USB-C Hub", "Webcam", "Headphones"],
    ),
    (
        "Pacific Components",
        "info@pacificcomp.com",
        "+1-650-555-0002",
        "Electronics",
        "US-based backup supplier focused on fast replenishment",
        ["Wireless Mouse", "USB-C Hub", "Power Bank", "Webcam"],
    ),
    (
        "Accessory Wholesalers",
        "orders@accwholesale.com",
        "+1-415-555-0003",
        "Accessories",
        "Wholesale accessories and packaging extras",
        ["Laptop Stand", "Phone Case", "Screen Protector", "Cable Organizer", "Power Bank"],
    ),
]

PARTNER_NAMES = [
    (
        "TechReview Blog",
        "partnership@techreview.com",
        "+1-555-0201",
        "Media",
        "Affiliate editorial partner for premium electronics",
        ["Mechanical Keyboard", "Webcam", "Headphones"],
        "affiliate",
        Decimal("12.00"),
    ),
    (
        "E-commerce Platform",
        "partners@ecomplatform.com",
        "+1-555-0202",
        "Platform",
        "Marketplace integration partner for broad catalog distribution",
        ["Wireless Mouse", "USB-C Hub", "Laptop Stand", "Phone Case", "Power Bank"],
        "revenue_share",
        Decimal("8.50"),
    ),
]


def generate_products():
    products = []
    for idx, (name, category, description, base_cost) in enumerate(PRODUCT_NAMES, start=1):
        margin_multiplier = Decimal("1.45") + Decimal(str((idx % 3) * 0.05))
        cost_price = (base_cost + Decimal(str((idx % 4) * 1.25))).quantize(Decimal("0.01"))
        selling_price = (cost_price * margin_multiplier).quantize(Decimal("0.01"))
        stock_number = 80 + (idx * 37)
        products.append(
            {
                "id": seed_uuid("product", name),
                "owner_id": OWNER_ID,
                "name": name,
                "description": description,
                "selling_price": str(selling_price),
                "cost_price": str(cost_price),
                "stock_number": stock_number,
                "product_link": f"https://example.com/products/{name.lower().replace(' ', '-')}",
                "category": category,
            }
        )
    return products


def generate_customers():
    customers = []
    for idx, (
        name,
        email,
        phone,
        company,
        preference,
        preferred_categories,
        preferred_channels,
        qty_range,
    ) in enumerate(CUSTOMER_NAMES, start=1):
        last_contact = REFERENCE_DATE - timedelta(days=idx * 9)
        customers.append(
            {
                "id": seed_uuid("customer", email),
                "owner_id": OWNER_ID,
                "name": name,
                "email": email,
                "phone": phone,
                "company": company,
                "status": "active",
                "preference": preference,
                "notes": f"Preferred categories: {', '.join(preferred_categories)}; channels: {', '.join(preferred_channels)}",
                "last_contact": last_contact.isoformat(),
                "_preferred_categories": preferred_categories,
                "_preferred_channels": preferred_channels,
                "_qty_range": qty_range,
            }
        )
    return customers


def generate_suppliers():
    suppliers = []
    for name, email, phone, category, notes, catalog in SUPPLIER_NAMES:
        suppliers.append(
            {
                "id": seed_uuid("supplier", email),
                "owner_id": OWNER_ID,
                "name": name,
                "email": email,
                "phone": phone,
                "category": category,
                "contract_notes": notes,
                "status": "active",
                "_catalog": catalog,
            }
        )
    return suppliers


def generate_partners():
    partners = []
    for (
        name,
        email,
        phone,
        partner_type,
        notes,
        product_focus,
        agreement_type,
        rev_share,
    ) in PARTNER_NAMES:
        partners.append(
            {
                "id": seed_uuid("partner", email),
                "owner_id": OWNER_ID,
                "name": name,
                "email": email,
                "phone": phone,
                "partner_type": partner_type,
                "notes": notes,
                "status": "active",
                "_product_focus": product_focus,
                "_agreement_type": agreement_type,
                "_revenue_share_pct": str(rev_share),
            }
        )
    return partners


def _products_by_name(products: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {p["name"]: p for p in products}


def generate_orders(customers, products):
    products_by_category: dict[str, list[dict[str, Any]]] = {}
    for p in products:
        products_by_category.setdefault(p["category"], []).append(p)

    orders = []

    for customer in customers:
        preferred_pool: list[dict[str, Any]] = []
        for category in customer["_preferred_categories"]:
            preferred_pool.extend(products_by_category.get(category, []))
        if not preferred_pool:
            preferred_pool = products

        for order_idx in range(1, RNG.randint(3, 5) + 1):
            product = RNG.choice(preferred_pool)
            qty_min, qty_max = customer["_qty_range"]
            quantity = RNG.randint(qty_min, qty_max)
            total_price = (Decimal(product["selling_price"]) * quantity).quantize(Decimal("0.01"))
            order_date = REFERENCE_DATE - timedelta(days=RNG.randint(2, 70))
            channel = RNG.choice(customer["_preferred_channels"])
            status = RNG.choices(
                ["pending", "shipped", "delivered", "cancelled"],
                weights=[2, 4, 6, 1],
                k=1,
            )[0]
            orders.append(
                {
                    "id": seed_uuid("order", customer["id"], str(order_idx), product["id"]),
                    "owner_id": OWNER_ID,
                    "customer_id": customer["id"],
                    "product_id": product["id"],
                    "quantity": quantity,
                    "total_price": str(total_price),
                    "order_date": order_date.isoformat(),
                    "status": status,
                    "channel": channel,
                }
            )

    used_product_ids = {o["product_id"] for o in orders}
    for idx, product in enumerate(products, start=1):
        if product["id"] in used_product_ids:
            continue
        customer = customers[idx % len(customers)]
        quantity = max(1, customer["_qty_range"][0])
        orders.append(
            {
                "id": seed_uuid("order-coverage", product["id"]),
                "owner_id": OWNER_ID,
                "customer_id": customer["id"],
                "product_id": product["id"],
                "quantity": quantity,
                "total_price": str(
                    (Decimal(product["selling_price"]) * quantity).quantize(Decimal("0.01"))
                ),
                "order_date": (REFERENCE_DATE - timedelta(days=idx)).isoformat(),
                "status": "delivered",
                "channel": customer["_preferred_channels"][0],
            }
        )

    return orders


def generate_supply_contracts(suppliers, products):
    products_by_name = _products_by_name(products)
    contracts = []
    covered_product_ids: set[str] = set()

    for supplier in suppliers:
        for product_name in supplier["_catalog"]:
            product = products_by_name.get(product_name)
            if not product:
                continue
            covered_product_ids.add(product["id"])

            cost = Decimal(product["cost_price"])
            discount = (
                Decimal("0.80") if supplier["category"] == product["category"] else Decimal("0.88")
            )
            supply_price = (cost * discount).quantize(Decimal("0.01"))
            contract_start = REFERENCE_DATE - timedelta(days=RNG.randint(120, 420))
            contract_end = contract_start + timedelta(days=RNG.randint(365, 730))

            contracts.append(
                {
                    "id": seed_uuid("supplier-product", supplier["id"], product["id"]),
                    "owner_id": OWNER_ID,
                    "supplier_id": supplier["id"],
                    "product_id": product["id"],
                    "supply_price": str(supply_price),
                    "stock_we_buy": RNG.randint(180, 1400),
                    "contract": f"{supplier['name']} annual procurement schedule",
                    "lead_time_days": RNG.randint(7, 24),
                    "contract_start": contract_start.isoformat(),
                    "contract_end": contract_end.isoformat(),
                    "is_active": "true",
                    "notes": f"Aligned to {supplier['category']} procurement lane for {product['name']}",
                }
            )

    suppliers_by_category: dict[str, list[dict[str, Any]]] = {}
    for s in suppliers:
        suppliers_by_category.setdefault(s["category"], []).append(s)

    for product in products:
        if product["id"] in covered_product_ids:
            continue
        fallback_suppliers = suppliers_by_category.get(product["category"]) or suppliers
        supplier = fallback_suppliers[0]
        contracts.append(
            {
                "id": seed_uuid("supplier-product-fallback", supplier["id"], product["id"]),
                "owner_id": OWNER_ID,
                "supplier_id": supplier["id"],
                "product_id": product["id"],
                "supply_price": str(
                    (Decimal(product["cost_price"]) * Decimal("0.86")).quantize(Decimal("0.01"))
                ),
                "stock_we_buy": 250,
                "contract": f"Fallback coverage for {product['name']}",
                "lead_time_days": 18,
                "contract_start": (REFERENCE_DATE - timedelta(days=200)).isoformat(),
                "contract_end": (REFERENCE_DATE + timedelta(days=420)).isoformat(),
                "is_active": "true",
                "notes": "Coverage contract to ensure fulfillment continuity",
            }
        )

    return contracts


def generate_partner_agreements(partners):
    agreements = []
    for partner in partners:
        start_date = REFERENCE_DATE - timedelta(days=RNG.randint(90, 300))
        end_date = start_date + timedelta(days=RNG.randint(365, 780))
        agreements.append(
            {
                "id": seed_uuid("partner-agreement", partner["id"]),
                "owner_id": OWNER_ID,
                "partner_id": partner["id"],
                "description": f"{partner['name']} agreement covering {partner['_agreement_type']} motions and campaign KPIs",
                "agreement_type": partner["_agreement_type"],
                "revenue_share_pct": partner["_revenue_share_pct"],
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "is_active": "true",
                "notes": "Monthly performance sync and quarterly optimization review",
            }
        )
    return agreements


def generate_partner_products(partners, products, agreements):
    products_by_name = _products_by_name(products)
    agreement_by_partner_id = {a["partner_id"]: a for a in agreements}
    relations = []
    for partner in partners:
        agreement = agreement_by_partner_id.get(partner["id"])
        for product_name in partner["_product_focus"]:
            product = products_by_name.get(product_name)
            if not product:
                continue
            relations.append(
                {
                    "id": seed_uuid("partner-product", partner["id"], product["id"]),
                    "owner_id": OWNER_ID,
                    "partner_id": partner["id"],
                    "product_id": product["id"],
                    "agreement_id": agreement["id"] if agreement else "",
                }
            )
    return relations


def _seeded_entities(customers, suppliers, partners):
    entities = []
    for role, rows in (("customer", customers), ("supplier", suppliers), ("partner", partners)):
        for row in rows:
            entities.append(
                {
                    "entity_role": role,
                    "entity_id": row["id"],
                    "name": row["name"],
                    "email": row.get("email") or "",
                }
            )
    return entities


def generate_external_identities(customers, suppliers, partners):
    identities = []
    for entity in _seeded_entities(customers, suppliers, partners):
        if not entity["email"]:
            continue
        identities.append(
            {
                "id": seed_uuid("external-identity", entity["entity_role"], entity["entity_id"]),
                "owner_id": OWNER_ID,
                "external_id": entity["email"].strip().lower(),
                "external_type": "email",
                "entity_role": entity["entity_role"],
                "entity_id": entity["entity_id"],
                "is_primary": "true",
                "identity_metadata": json.dumps(
                    {"source": "seed", "entity_name": entity["name"]}, separators=(",", ":")
                ),
            }
        )
    return identities


def generate_conversation_threads(customers, suppliers, partners):
    seed_pool = [
        ("customer", customers[0], "email", "Order ETA and restock schedule"),
        ("customer", customers[1], "email", "Bulk order change request"),
        ("supplier", suppliers[0], "email", "Lead time adjustment"),
        ("partner", partners[0], "email", "Campaign performance follow-up"),
        ("customer", customers[4], "email", "Approval needed for high-value quote"),
    ]
    threads = []
    for idx, (role, entity, channel, title) in enumerate(seed_pool, start=1):
        threads.append(
            {
                "id": seed_uuid("conversation-thread", str(idx), entity["id"]),
                "owner_id": OWNER_ID,
                "thread_type": "external_sender",
                "title": title,
                "sender_external_id": entity.get("email", "").strip().lower(),
                "sender_name": entity["name"],
                "sender_role": role,
                "sender_channel": channel,
            }
        )
    return threads


def generate_messages(threads):
    messages = []
    templates = [
        (
            "inbound",
            "Could you confirm availability and delivery timing for this week?",
        ),
        (
            "outbound",
            "Yes, we can fulfill from current stock and share shipment confirmation shortly.",
        ),
    ]

    for thread in threads:
        for idx, (direction, content) in enumerate(templates, start=1):
            messages.append(
                {
                    "id": seed_uuid("message", thread["id"], direction, str(idx)),
                    "owner_id": OWNER_ID,
                    "conversation_thread_id": thread["id"],
                    "sender_id": thread["sender_external_id"],
                    "sender_name": thread["sender_name"],
                    "sender_role": thread["sender_role"],
                    "direction": direction,
                    "content": content,
                }
            )

    approval_thread = threads[-1]
    messages.append(
        {
            "id": seed_uuid("message", approval_thread["id"], "approved-reply"),
            "owner_id": OWNER_ID,
            "conversation_thread_id": approval_thread["id"],
            "sender_id": approval_thread["sender_external_id"],
            "sender_name": approval_thread["sender_name"],
            "sender_role": approval_thread["sender_role"],
            "direction": "outbound",
            "content": "We can proceed once procurement approval is finalized. I'll send the formal quote next.",
        }
    )

    return messages


def generate_memory_update_proposals(customers):
    pending_customer = customers[1]
    approved_customer = customers[3]

    return [
        {
            "id": seed_uuid("memory-proposal", "pending", pending_customer["id"]),
            "owner_id": OWNER_ID,
            "target_table": "customers",
            "target_id": pending_customer["id"],
            "proposed_content": json.dumps(
                [
                    {
                        "sender_id": pending_customer["email"],
                        "sender_name": pending_customer["name"],
                        "sender_role": "customer",
                        "memory_type": "preference",
                        "content": "RetailCo requested pallet-level packaging and Friday-only dock delivery.",
                        "summary": "RetailCo prefers palletized Friday deliveries",
                        "tags": ["logistics", "bulk-order"],
                        "importance": 0.82,
                    }
                ],
                separators=(",", ":"),
            ),
            "reason": "Detected stable logistics preference from recent thread",
            "risk_level": "medium",
            "status": "pending",
        },
        {
            "id": seed_uuid("memory-proposal", "approved", approved_customer["id"]),
            "owner_id": OWNER_ID,
            "target_table": "customers",
            "target_id": approved_customer["id"],
            "proposed_content": json.dumps(
                [
                    {
                        "sender_id": approved_customer["email"],
                        "sender_name": approved_customer["name"],
                        "sender_role": "customer",
                        "memory_type": "billing",
                        "content": "Startup.io accepted prepaid terms for first two replenishment cycles.",
                        "summary": "Startup.io temporary prepaid billing window",
                        "tags": ["finance", "terms"],
                        "importance": 0.65,
                    }
                ],
                separators=(",", ":"),
            ),
            "reason": "Owner previously approved this billing update",
            "risk_level": "low",
            "status": "approved",
        },
    ]


def generate_held_replies(threads):
    risky_thread = threads[1]
    high_risk_thread = threads[4]

    return [
        {
            "id": seed_uuid("held-reply", "pending", risky_thread["id"]),
            "owner_id": OWNER_ID,
            "thread_id": risky_thread["id"],
            "sender_id": risky_thread["sender_external_id"],
            "sender_name": risky_thread["sender_name"],
            "sender_role": risky_thread["sender_role"],
            "reply_text": "We can authorize a 25% one-time discount and bypass standard credit checks.",
            "risk_level": "high",
            "risk_flags": json.dumps(
                ["pricing-policy-breach", "credit-policy-breach"], separators=(",", ":")
            ),
            "status": "pending",
            "reviewer_notes": "",
        },
        {
            "id": seed_uuid("held-reply", "approved", high_risk_thread["id"]),
            "owner_id": OWNER_ID,
            "thread_id": high_risk_thread["id"],
            "sender_id": high_risk_thread["sender_external_id"],
            "sender_name": high_risk_thread["sender_name"],
            "sender_role": high_risk_thread["sender_role"],
            "reply_text": "We can provide a preliminary quote after legal review confirms partner terms.",
            "risk_level": "medium",
            "risk_flags": json.dumps(["legal-review-required"], separators=(",", ":")),
            "status": "approved",
            "reviewer_notes": "Approved with legal gate.",
        },
    ]


def generate_reply_review_records(held_replies, threads, messages):
    thread_by_id = {t["id"]: t for t in threads}
    approved_message = next(
        m for m in messages if m["id"] == seed_uuid("message", threads[4]["id"], "approved-reply")
    )

    records = []
    for held in held_replies:
        thread = thread_by_id.get(held["thread_id"])
        thread_sender_name = thread["sender_name"] if thread else held["sender_name"]
        pending = held["status"] == "pending"
        records.append(
            {
                "id": seed_uuid("reply-review", held["id"]),
                "owner_id": OWNER_ID,
                "trace_id": seed_uuid("trace", held["id"]),
                "thread_id": held["thread_id"],
                "sender_id": held["sender_id"],
                "sender_name": held["sender_name"],
                "sender_role": held["sender_role"],
                "raw_message": f"{thread_sender_name} requested policy exception for order terms.",
                "reply_text": held["reply_text"],
                "risk_level": held["risk_level"],
                "risk_flags": held["risk_flags"],
                "approval_rule_flags": json.dumps(
                    ["human-approval-required"], separators=(",", ":")
                ),
                "requires_approval": "true",
                "final_decision": "held_pending_review" if pending else "approved_and_sent",
                "review_label": "needs-owner-review" if pending else "approved",
                "reviewer_reason": "Pending owner confirmation"
                if pending
                else "Approved with constraints",
                "held_reply_id": held["id"],
                "message_id": "" if pending else approved_message["id"],
            }
        )
    return records


def generate_pending_approvals(memory_proposals, held_replies):
    pending_memory = next(p for p in memory_proposals if p["status"] == "pending")
    pending_replies = [h for h in held_replies if h["status"] == "pending"]

    approvals = [
        {
            "id": seed_uuid("pending-approval", "memory", pending_memory["id"]),
            "owner_id": OWNER_ID,
            "title": "Memory update requires review",
            "sender": "Memory Agent",
            "preview": "RetailCo requested pallet-level packaging and Friday-only dock delivery.",
            "proposal_type": "memory-update",
            "risk_level": pending_memory["risk_level"],
            "status": "pending",
            "proposal_id": pending_memory["id"],
            "held_reply_id": "",
        }
    ]

    for held in pending_replies:
        approvals.append(
            {
                "id": seed_uuid("pending-approval", "reply", held["id"]),
                "owner_id": OWNER_ID,
                "title": f"Reply requires approval ({held['risk_level']} risk)",
                "sender": held["sender_name"],
                "preview": held["reply_text"][:200],
                "proposal_type": "reply-approval",
                "risk_level": held["risk_level"],
                "status": "pending",
                "proposal_id": "",
                "held_reply_id": held["id"],
            }
        )

    return approvals


def write_csv(filename, rows, fieldnames):
    filepath = SEED_DIR / filename
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} rows → {filename}")


def _strip_internal_fields(rows):
    cleaned = []
    for row in rows:
        cleaned.append({k: v for k, v in row.items() if not k.startswith("_")})
    return cleaned


def main():
    SEED_DIR.mkdir(parents=True, exist_ok=True)

    products = generate_products()
    customers = generate_customers()
    suppliers = generate_suppliers()
    partners = generate_partners()

    orders = generate_orders(customers, products)
    supply_contracts = generate_supply_contracts(suppliers, products)
    partner_agreements = generate_partner_agreements(partners)
    partner_products = generate_partner_products(partners, products, partner_agreements)

    external_identities = generate_external_identities(customers, suppliers, partners)
    conversation_threads = generate_conversation_threads(customers, suppliers, partners)
    messages = generate_messages(conversation_threads)
    memory_update_proposals = generate_memory_update_proposals(customers)
    held_replies = generate_held_replies(conversation_threads)
    reply_review_records = generate_reply_review_records(
        held_replies, conversation_threads, messages
    )
    pending_approvals = generate_pending_approvals(memory_update_proposals, held_replies)

    write_csv(
        "products.csv",
        _strip_internal_fields(products),
        [
            "id",
            "owner_id",
            "name",
            "description",
            "selling_price",
            "cost_price",
            "stock_number",
            "product_link",
            "category",
        ],
    )

    write_csv(
        "customers.csv",
        _strip_internal_fields(customers),
        [
            "id",
            "owner_id",
            "name",
            "email",
            "phone",
            "company",
            "status",
            "preference",
            "notes",
            "last_contact",
        ],
    )

    write_csv(
        "suppliers.csv",
        _strip_internal_fields(suppliers),
        ["id", "owner_id", "name", "email", "phone", "category", "contract_notes", "status"],
    )

    write_csv(
        "partners.csv",
        _strip_internal_fields(partners),
        ["id", "owner_id", "name", "email", "phone", "partner_type", "notes", "status"],
    )

    write_csv(
        "orders.csv",
        orders,
        [
            "id",
            "owner_id",
            "customer_id",
            "product_id",
            "quantity",
            "total_price",
            "order_date",
            "status",
            "channel",
        ],
    )

    write_csv(
        "supply_contracts.csv",
        supply_contracts,
        [
            "id",
            "owner_id",
            "supplier_id",
            "product_id",
            "supply_price",
            "stock_we_buy",
            "contract",
            "lead_time_days",
            "contract_start",
            "contract_end",
            "is_active",
            "notes",
        ],
    )

    write_csv(
        "partner_agreements.csv",
        partner_agreements,
        [
            "id",
            "owner_id",
            "partner_id",
            "description",
            "agreement_type",
            "revenue_share_pct",
            "start_date",
            "end_date",
            "is_active",
            "notes",
        ],
    )

    write_csv(
        "partner_products.csv",
        partner_products,
        ["id", "owner_id", "partner_id", "product_id", "agreement_id"],
    )

    write_csv(
        "external_identities.csv",
        external_identities,
        [
            "id",
            "owner_id",
            "external_id",
            "external_type",
            "entity_role",
            "entity_id",
            "is_primary",
            "identity_metadata",
        ],
    )

    write_csv(
        "conversation_threads.csv",
        conversation_threads,
        [
            "id",
            "owner_id",
            "thread_type",
            "title",
            "sender_external_id",
            "sender_name",
            "sender_role",
            "sender_channel",
        ],
    )

    write_csv(
        "messages.csv",
        messages,
        [
            "id",
            "owner_id",
            "conversation_thread_id",
            "sender_id",
            "sender_name",
            "sender_role",
            "direction",
            "content",
        ],
    )

    write_csv(
        "memory_update_proposals.csv",
        memory_update_proposals,
        [
            "id",
            "owner_id",
            "target_table",
            "target_id",
            "proposed_content",
            "reason",
            "risk_level",
            "status",
        ],
    )

    write_csv(
        "held_replies.csv",
        held_replies,
        [
            "id",
            "owner_id",
            "thread_id",
            "sender_id",
            "sender_name",
            "sender_role",
            "reply_text",
            "risk_level",
            "risk_flags",
            "status",
            "reviewer_notes",
        ],
    )

    write_csv(
        "reply_review_records.csv",
        reply_review_records,
        [
            "id",
            "owner_id",
            "trace_id",
            "thread_id",
            "sender_id",
            "sender_name",
            "sender_role",
            "raw_message",
            "reply_text",
            "risk_level",
            "risk_flags",
            "approval_rule_flags",
            "requires_approval",
            "final_decision",
            "review_label",
            "reviewer_reason",
            "held_reply_id",
            "message_id",
        ],
    )

    write_csv(
        "pending_approvals.csv",
        pending_approvals,
        [
            "id",
            "owner_id",
            "title",
            "sender",
            "preview",
            "proposal_type",
            "risk_level",
            "status",
            "proposal_id",
            "held_reply_id",
        ],
    )

    print("Seed data generation complete.")


if __name__ == "__main__":
    main()
