import csv
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).parent.parent / "data" / "seed"
OWNERS_FILE = SEED_DIR / "owners.json"
REFERENCE_DATE = date(2026, 4, 1)

PRODUCT_TEMPLATES = [
    (
        "Wireless Mouse",
        "Electronics",
        "Reliable wireless mouse for daily work",
        Decimal("29.90"),
        Decimal("17.50"),
        36,
    ),
    (
        "USB-C Hub",
        "Electronics",
        "Compact USB-C hub for modern laptops",
        Decimal("39.90"),
        Decimal("24.00"),
        28,
    ),
    (
        "Phone Case",
        "Accessories",
        "Protective phone case with shock absorption",
        Decimal("16.50"),
        Decimal("7.80"),
        52,
    ),
    (
        "Power Bank",
        "Electronics",
        "Portable charger for everyday use",
        Decimal("42.00"),
        Decimal("25.25"),
        24,
    ),
    (
        "Mechanical Keyboard",
        "Electronics",
        "Mechanical keyboard with tactile switches",
        Decimal("79.00"),
        Decimal("49.50"),
        18,
    ),
    (
        "Laptop Stand",
        "Accessories",
        "Adjustable aluminum stand for desks",
        Decimal("31.50"),
        Decimal("18.20"),
        20,
    ),
    (
        "Webcam",
        "Electronics",
        "1080p webcam for meetings and streaming",
        Decimal("54.00"),
        Decimal("33.40"),
        16,
    ),
    (
        "Headphones",
        "Electronics",
        "Wireless over-ear headphones with ANC",
        Decimal("96.00"),
        Decimal("61.00"),
        14,
    ),
    (
        "Desk Lamp",
        "Accessories",
        "LED desk lamp with dimmable brightness",
        Decimal("27.00"),
        Decimal("15.10"),
        22,
    ),
]


def seed_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "seed-data:" + ":".join(parts)))


def load_owners() -> list[dict[str, str]]:
    if not OWNERS_FILE.exists():
        raise FileNotFoundError(
            f"{OWNERS_FILE} not found. Generate owner auth users first so seed data can bind to real owner ids."
        )
    owners = json.loads(OWNERS_FILE.read_text())
    if not owners:
        raise ValueError("owners.json is empty")
    return owners


def write_csv(filename: str, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    filepath = SEED_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} rows -> {filename}")


def owner_index(owner: dict[str, str]) -> str:
    return owner["label"].replace("owner", "")


def generate_products(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for owner in owners:
        idx = owner_index(owner)
        for (
            product_name,
            category,
            description,
            selling_price,
            cost_price,
            stock,
        ) in PRODUCT_TEMPLATES:
            products.append(
                {
                    "id": seed_uuid("product", owner["label"], product_name),
                    "owner_id": owner["id"],
                    "name": f"{product_name} {idx}",
                    "description": f"{description} for {owner['email']}",
                    "selling_price": str(selling_price),
                    "cost_price": str(cost_price),
                    "stock_number": stock,
                    "product_link": f"https://example.com/{owner['label']}/{product_name.lower().replace(' ', '-')}",
                    "category": category,
                }
            )
    return products


def generate_customers(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        idx = owner_index(owner)
        rows.append(
            {
                "id": seed_uuid("customer", owner["label"]),
                "owner_id": owner["id"],
                "name": f"Customer {idx}",
                "email": f"customer{idx}@gmail.com",
                "phone": f"+15550010{idx}",
                "company": f"Customer {idx} Co",
                "status": "active",
                "preference": "Prefers product updates by email",
                "notes": f"Seed customer under {owner['email']}",
                "telegram_user_id": "",
                "telegram_username": f"customer{idx}",
                "telegram_chat_id": "",
                "last_contact": (REFERENCE_DATE - timedelta(days=int(idx))).isoformat(),
            }
        )
    return rows


def generate_suppliers(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        idx = owner_index(owner)
        rows.append(
            {
                "id": seed_uuid("supplier", owner["label"]),
                "owner_id": owner["id"],
                "name": f"Supplier {idx}",
                "email": f"supplier{idx}@gmail.com",
                "phone": f"+16660010{idx}",
                "category": "Electronics",
                "contract_notes": f"Primary supplier for owner {idx}",
                "status": "active",
            }
        )
    return rows


def generate_partners(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        idx = owner_index(owner)
        rows.append(
            {
                "id": seed_uuid("partner", owner["label"]),
                "owner_id": owner["id"],
                "name": f"Partner {idx}",
                "email": f"partner{idx}@gmail.com",
                "phone": f"+17770010{idx}",
                "partner_type": "affiliate",
                "notes": f"Seed partner under {owner['email']}",
                "status": "active",
            }
        )
    return rows


def generate_investors(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        idx = owner_index(owner)
        rows.append(
            {
                "id": seed_uuid("investor", owner["label"]),
                "owner_id": owner["id"],
                "name": f"Investor {idx}",
                "email": f"investor{idx}@gmail.com",
                "phone": f"+18880010{idx}",
                "focus": "Growth and monthly sales performance",
                "notes": f"Seed investor under {owner['email']}",
                "status": "active",
            }
        )
    return rows


def generate_orders(
    customers: list[dict[str, Any]], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    products_by_owner: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        products_by_owner.setdefault(product["owner_id"], []).append(product)

    for customer in customers:
        owner_products = products_by_owner[customer["owner_id"]]
        first_product = owner_products[0]
        second_product = owner_products[1]
        rows.append(
            {
                "id": seed_uuid("order", customer["id"], "today"),
                "owner_id": customer["owner_id"],
                "customer_id": customer["id"],
                "product_id": first_product["id"],
                "quantity": 1,
                "total_price": first_product["selling_price"],
                "order_date": REFERENCE_DATE.isoformat(),
                "status": "paid",
                "channel": "website",
            }
        )
        rows.append(
            {
                "id": seed_uuid("order", customer["id"], "last-month"),
                "owner_id": customer["owner_id"],
                "customer_id": customer["id"],
                "product_id": second_product["id"],
                "quantity": 2,
                "total_price": str(
                    (Decimal(second_product["selling_price"]) * 2).quantize(Decimal("0.01"))
                ),
                "order_date": (REFERENCE_DATE - timedelta(days=31)).isoformat(),
                "status": "paid",
                "channel": "telegram",
            }
        )
    return rows


def generate_supply_contracts(
    suppliers: list[dict[str, Any]], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    products_by_owner: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        products_by_owner.setdefault(product["owner_id"], []).append(product)
    for supplier in suppliers:
        for product in products_by_owner[supplier["owner_id"]][:2]:
            rows.append(
                {
                    "id": seed_uuid("supplier-product", supplier["id"], product["id"]),
                    "owner_id": supplier["owner_id"],
                    "supplier_id": supplier["id"],
                    "product_id": product["id"],
                    "supply_price": product["cost_price"],
                    "stock_we_buy": 20,
                    "contract": f"Supply agreement for {product['name']}",
                    "lead_time_days": 7,
                    "contract_start": (REFERENCE_DATE - timedelta(days=30)).isoformat(),
                    "contract_end": (REFERENCE_DATE + timedelta(days=365)).isoformat(),
                    "is_active": "true",
                    "notes": f"Seed supplier contract under owner {supplier['owner_id']}",
                }
            )
    return rows


def generate_partner_agreements(partners: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for partner in partners:
        rows.append(
            {
                "id": seed_uuid("partner-agreement", partner["id"]),
                "owner_id": partner["owner_id"],
                "partner_id": partner["id"],
                "description": f"Partnership agreement for {partner['name']}",
                "agreement_type": "affiliate",
                "revenue_share_pct": "10.00",
                "start_date": (REFERENCE_DATE - timedelta(days=45)).isoformat(),
                "end_date": (REFERENCE_DATE + timedelta(days=365)).isoformat(),
                "is_active": "true",
                "notes": f"Seed partner agreement under owner {partner['owner_id']}",
            }
        )
    return rows


def generate_partner_products(
    partners: list[dict[str, Any]], products: list[dict[str, Any]], agreements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    agreement_by_partner = {agreement["partner_id"]: agreement for agreement in agreements}
    products_by_owner: dict[str, list[dict[str, Any]]] = {}
    for product in products:
        products_by_owner.setdefault(product["owner_id"], []).append(product)

    rows: list[dict[str, Any]] = []
    for partner in partners:
        agreement = agreement_by_partner[partner["id"]]
        for product in products_by_owner[partner["owner_id"]][:2]:
            rows.append(
                {
                    "id": seed_uuid("partner-product", partner["id"], product["id"]),
                    "owner_id": partner["owner_id"],
                    "partner_id": partner["id"],
                    "product_id": product["id"],
                    "agreement_id": agreement["id"],
                }
            )
    return rows


def generate_external_identities(
    customers: list[dict[str, Any]],
    suppliers: list[dict[str, Any]],
    partners: list[dict[str, Any]],
    investors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, entries in (
        ("customer", customers),
        ("supplier", suppliers),
        ("partner", partners),
        ("investor", investors),
    ):
        for entry in entries:
            rows.append(
                {
                    "id": seed_uuid("external-identity-email", role, entry["id"]),
                    "owner_id": entry["owner_id"],
                    "external_id": entry["email"].lower(),
                    "external_type": "email",
                    "entity_role": role,
                    "entity_id": entry["id"],
                    "is_primary": "true",
                    "identity_metadata": json.dumps(
                        {"source": "seed", "entity_name": entry["name"]}, separators=(",", ":")
                    ),
                }
            )
            rows.append(
                {
                    "id": seed_uuid("external-identity-phone", role, entry["id"]),
                    "owner_id": entry["owner_id"],
                    "external_id": entry["phone"].replace("-", "").replace(" ", ""),
                    "external_type": "phone",
                    "entity_role": role,
                    "entity_id": entry["id"],
                    "is_primary": "false",
                    "identity_metadata": json.dumps(
                        {"source": "seed", "entity_name": entry["name"]}, separators=(",", ":")
                    ),
                }
            )
    return rows


def generate_conversation_threads(customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for customer in customers:
        rows.append(
            {
                "id": seed_uuid("conversation-thread", customer["id"]),
                "owner_id": customer["owner_id"],
                "thread_type": "external_sender",
                "title": f"{customer['name']} support thread",
                "sender_external_id": customer["email"].lower(),
                "sender_name": customer["name"],
                "sender_role": "customer",
                "sender_channel": "website",
            }
        )
    return rows


def generate_messages(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for thread in threads:
        rows.append(
            {
                "id": seed_uuid("message", thread["id"], "inbound"),
                "owner_id": thread["owner_id"],
                "conversation_thread_id": thread["id"],
                "sender_id": thread["sender_external_id"],
                "sender_name": thread["sender_name"],
                "sender_role": thread["sender_role"],
                "direction": "inbound",
                "content": "Do you have this item in stock?",
            }
        )
        rows.append(
            {
                "id": seed_uuid("message", thread["id"], "outbound"),
                "owner_id": thread["owner_id"],
                "conversation_thread_id": thread["id"],
                "sender_id": thread["sender_external_id"],
                "sender_name": thread["sender_name"],
                "sender_role": thread["sender_role"],
                "direction": "outbound",
                "content": "Yes, the item is currently available and ready to order.",
            }
        )
    return rows


def empty_rows() -> list[dict[str, Any]]:
    return []


def main() -> None:
    owners = load_owners()
    products = generate_products(owners)
    customers = generate_customers(owners)
    suppliers = generate_suppliers(owners)
    partners = generate_partners(owners)
    investors = generate_investors(owners)
    orders = generate_orders(customers, products)
    supply_contracts = generate_supply_contracts(suppliers, products)
    partner_agreements = generate_partner_agreements(partners)
    partner_products = generate_partner_products(partners, products, partner_agreements)
    external_identities = generate_external_identities(customers, suppliers, partners, investors)
    conversation_threads = generate_conversation_threads(customers)
    messages = generate_messages(conversation_threads)

    write_csv(
        "products.csv",
        products,
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
        customers,
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
            "telegram_user_id",
            "telegram_username",
            "telegram_chat_id",
            "last_contact",
        ],
    )
    write_csv(
        "suppliers.csv",
        suppliers,
        ["id", "owner_id", "name", "email", "phone", "category", "contract_notes", "status"],
    )
    write_csv(
        "partners.csv",
        partners,
        ["id", "owner_id", "name", "email", "phone", "partner_type", "notes", "status"],
    )
    write_csv(
        "investors.csv",
        investors,
        ["id", "owner_id", "name", "email", "phone", "focus", "notes", "status"],
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
        empty_rows(),
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
        empty_rows(),
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
        empty_rows(),
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
        empty_rows(),
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
