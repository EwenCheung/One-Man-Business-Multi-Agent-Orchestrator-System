"""
Seed Data Generator

Generates realistic CSV seed data files for populating the database.
Creates customers, products, suppliers, partners, orders, and relationships.

Usage:
    uv run python backend/db/generate_seed_data.py
"""

import csv
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

SEED_DIR = Path(__file__).parent.parent / "data" / "seed"
OWNER_ID = "4c116430-f683-4a8a-91f7-546fa8bc5d76"

PRODUCT_NAMES = [
    (
        "Wireless Mouse",
        "Electronics",
        "Ergonomic wireless mouse with 2.4GHz connectivity and long battery life",
    ),
    (
        "Mechanical Keyboard",
        "Electronics",
        "RGB backlit mechanical keyboard with Cherry MX switches",
    ),
    ("USB-C Hub", "Electronics", "7-in-1 USB-C hub with HDMI, USB 3.0, SD card reader"),
    ("Laptop Stand", "Accessories", "Adjustable aluminum laptop stand for ergonomic viewing"),
    ("Phone Case", "Accessories", "Shockproof silicone phone case with raised edges"),
    ("Screen Protector", "Accessories", "Tempered glass screen protector 9H hardness"),
    ("Webcam", "Electronics", "1080p HD webcam with autofocus and dual microphone"),
    ("Headphones", "Electronics", "Noise-cancelling over-ear wireless headphones"),
    ("Power Bank", "Electronics", "20000mAh portable power bank with fast charging"),
    ("Cable Organizer", "Accessories", "Desktop cable management box with multiple slots"),
]

CUSTOMER_NAMES = [
    (
        "Alice Chen",
        "alice@techcorp.com",
        "+1-555-0101",
        "TechCorp Inc",
        "Prefers expedited shipping",
    ),
    (
        "Bob Martinez",
        "bob@retailco.com",
        "+1-555-0102",
        "RetailCo LLC",
        "Bulk orders only, net-30 terms",
    ),
    (
        "Carol White",
        "carol@designstudio.com",
        "+1-555-0103",
        "Design Studio",
        "Needs custom packaging",
    ),
    (
        "David Kim",
        "david@startup.io",
        "+1-555-0104",
        "Startup.io",
        "Price-sensitive, flexible on delivery",
    ),
    (
        "Emma Brown",
        "emma@enterprise.com",
        "+1-555-0105",
        "Enterprise Solutions",
        "Requires invoicing before shipment",
    ),
]

SUPPLIER_NAMES = [
    (
        "Global Electronics Supply",
        "sales@globalsupply.com",
        "+86-21-5555-0001",
        "Electronics",
        "Primary supplier for computer peripherals",
    ),
    (
        "Pacific Components",
        "info@pacificcomp.com",
        "+1-650-555-0002",
        "Electronics",
        "US-based component distributor",
    ),
    (
        "Accessory Wholesalers",
        "orders@accwholesale.com",
        "+1-415-555-0003",
        "Accessories",
        "Wholesale accessories and cases",
    ),
]

PARTNER_NAMES = [
    (
        "TechReview Blog",
        "partnership@techreview.com",
        "+1-555-0201",
        "Media",
        "Affiliate marketing partnership",
    ),
    (
        "E-commerce Platform",
        "partners@ecomplatform.com",
        "+1-555-0202",
        "Platform",
        "Marketplace integration partner",
    ),
]


def generate_products():
    products = []
    for i, (name, category, description) in enumerate(PRODUCT_NAMES):
        cost_price = Decimal(str(random.uniform(10.00, 100.00))).quantize(Decimal("0.01"))
        selling_price = (cost_price * Decimal("1.5")).quantize(Decimal("0.01"))
        products.append(
            {
                "id": str(uuid.uuid4()),
                "owner_id": OWNER_ID,
                "name": name,
                "description": description,
                "selling_price": str(selling_price),
                "cost_price": str(cost_price),
                "stock_number": random.randint(50, 500),
                "product_link": f"https://example.com/products/{name.lower().replace(' ', '-')}",
                "category": category,
            }
        )
    return products


def generate_customers():
    customers = []
    for name, email, phone, company, preference in CUSTOMER_NAMES:
        last_contact = date.today() - timedelta(days=random.randint(1, 90))
        customers.append(
            {
                "id": str(uuid.uuid4()),
                "owner_id": OWNER_ID,
                "name": name,
                "email": email,
                "phone": phone,
                "company": company,
                "status": "active",
                "preference": preference,
                "notes": f"Customer since {(date.today() - timedelta(days=random.randint(180, 720))).isoformat()}",
                "last_contact": last_contact.isoformat(),
            }
        )
    return customers


def generate_suppliers():
    suppliers = []
    for name, email, phone, category, notes in SUPPLIER_NAMES:
        suppliers.append(
            {
                "id": str(uuid.uuid4()),
                "owner_id": OWNER_ID,
                "name": name,
                "email": email,
                "phone": phone,
                "category": category,
                "contract_notes": notes,
                "status": "active",
            }
        )
    return suppliers


def generate_partners():
    partners = []
    for name, email, phone, partner_type, notes in PARTNER_NAMES:
        partners.append(
            {
                "id": str(uuid.uuid4()),
                "owner_id": OWNER_ID,
                "name": name,
                "email": email,
                "phone": phone,
                "partner_type": partner_type,
                "notes": notes,
                "status": "active",
            }
        )
    return partners


def generate_orders(customers, products):
    orders = []
    for _ in range(20):
        customer = random.choice(customers)
        product = random.choice(products)
        quantity = random.randint(1, 10)
        total_price = Decimal(product["selling_price"]) * quantity
        order_date = date.today() - timedelta(days=random.randint(0, 60))
        status_options = ["pending", "shipped", "delivered", "cancelled"]
        orders.append(
            {
                "id": str(uuid.uuid4()),
                "owner_id": OWNER_ID,
                "customer_id": customer["id"],
                "product_id": product["id"],
                "quantity": quantity,
                "total_price": str(total_price.quantize(Decimal("0.01"))),
                "order_date": order_date.isoformat(),
                "status": random.choice(status_options),
                "channel": random.choice(["website", "email", "phone"]),
            }
        )
    return orders


def generate_supply_contracts(suppliers, products):
    contracts = []
    for supplier in suppliers:
        for product in random.sample(products, k=min(4, len(products))):
            supply_price = (Decimal(product["cost_price"]) * Decimal("0.8")).quantize(
                Decimal("0.01")
            )
            contract_start = date.today() - timedelta(days=random.randint(30, 365))
            contract_end = contract_start + timedelta(days=random.randint(180, 730))
            contracts.append(
                {
                    "id": str(uuid.uuid4()),
                    "owner_id": OWNER_ID,
                    "supplier_id": supplier["id"],
                    "product_id": product["id"],
                    "supply_price": str(supply_price),
                    "stock_we_buy": random.randint(100, 1000),
                    "contract": f"Agreement {contract_start.year}-{random.randint(1000, 9999)}",
                    "lead_time_days": random.randint(7, 30),
                    "contract_start": contract_start.isoformat(),
                    "contract_end": contract_end.isoformat(),
                    "is_active": "true",
                    "notes": f"Standard supply agreement for {product['name']}",
                }
            )
    return contracts


def generate_partner_agreements(partners):
    agreements = []
    for partner in partners:
        start_date = date.today() - timedelta(days=random.randint(30, 180))
        end_date = start_date + timedelta(days=random.randint(365, 730))
        agreements.append(
            {
                "id": str(uuid.uuid4()),
                "owner_id": OWNER_ID,
                "partner_id": partner["id"],
                "description": f"Partnership agreement with {partner['name']} for revenue sharing and co-marketing",
                "agreement_type": random.choice(["revenue_share", "affiliate", "co_marketing"]),
                "revenue_share_pct": str(
                    Decimal(str(random.uniform(5.0, 20.0))).quantize(Decimal("0.01"))
                ),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "is_active": "true",
                "notes": f"Quarterly performance reviews required",
            }
        )
    return agreements


def generate_partner_products(partners, products, agreements):
    relations = []
    for partner in partners:
        partner_agreements = [a for a in agreements if a["partner_id"] == partner["id"]]
        agreement = partner_agreements[0] if partner_agreements else None

        for product in random.sample(products, k=min(3, len(products))):
            relations.append(
                {
                    "id": str(uuid.uuid4()),
                    "owner_id": OWNER_ID,
                    "partner_id": partner["id"],
                    "product_id": product["id"],
                    "agreement_id": agreement["id"] if agreement else "",
                }
            )
    return relations


def write_csv(filename, rows, fieldnames):
    filepath = SEED_DIR / filename
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} rows → {filename}")


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

    print("Seed data generation complete.")


if __name__ == "__main__":
    main()
