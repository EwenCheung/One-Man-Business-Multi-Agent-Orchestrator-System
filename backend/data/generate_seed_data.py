"""
Seed Data Generator

Generates realistic synthetic CSV data for a one-man physical goods e-commerce
business based in Singapore. Output files are written to backend/data/seed/.

All entities (products, suppliers, partners, customers) are hardcoded for
reproducibility. Orders, supply contracts, and partner products are derived
programmatically from those fixed entities.

Usage:
    uv run python backend/data/generate_seed_data.py
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED_DIR = Path(__file__).parent / "seed"

# ─── Hardcoded entity data ────────────────────────────────────────────────────

PRODUCT_CATALOG = [
    # (name, category, cost_price, selling_price, description)
    ("Wireless Bluetooth Earbuds",      "Electronics",      12.50, 29.99, "Compact earbuds with noise cancellation and 8-hour battery life"),
    ("USB-C Fast Charger 65W",          "Electronics",       8.00, 19.99, "GaN charger compatible with laptops, tablets, and phones"),
    ("Portable Power Bank 20000mAh",    "Electronics",      15.00, 34.99, "Slim power bank with dual USB-A and USB-C output"),
    ("Mechanical Keyboard RGB",         "Electronics",      22.00, 54.99, "Hot-swappable switches with per-key RGB lighting"),
    ("Wireless Gaming Mouse",           "Electronics",      10.00, 27.99, "Ergonomic design with adjustable DPI up to 16000"),
    ("Laptop Stand Aluminum",           "Electronics",       9.50, 24.99, "Adjustable height stand with ventilation slots"),
    ("4K Webcam with Mic",              "Electronics",      18.00, 44.99, "Auto-focus webcam with built-in noise-cancelling microphone"),
    ("Smart LED Desk Lamp",             "Electronics",      11.00, 29.99, "Touch-controlled lamp with 5 brightness levels and USB charging port"),
    ("Noise Cancelling Headphones",     "Electronics",      30.00, 74.99, "Over-ear headphones with ANC and 30-hour battery"),
    ("HDMI to USB-C Adapter",           "Electronics",       4.50, 14.99, "4K@60Hz adapter for MacBook and Windows laptops"),
    ("Men's Cotton T-Shirt",            "Apparel",           4.00, 14.99, "Premium cotton crew neck tee available in 8 colours"),
    ("Women's Running Leggings",        "Apparel",           7.00, 24.99, "High-waist moisture-wicking leggings with side pocket"),
    ("Unisex Zip Hoodie",               "Apparel",          12.00, 34.99, "Heavyweight fleece hoodie with metal YKK zipper"),
    ("Baseball Cap Embroidered",        "Apparel",           3.50, 12.99, "Adjustable snapback with embroidered logo"),
    ("Waterproof Hiking Jacket",        "Apparel",          25.00, 64.99, "Seam-sealed jacket with breathable membrane"),
    ("Bamboo Fiber Socks 6-Pack",       "Apparel",           3.00, 11.99, "Anti-bacterial bamboo socks with reinforced heel and toe"),
    ("Stainless Steel Water Bottle 750ml", "Home & Kitchen",  5.00, 16.99, "Double-wall vacuum insulated keeps drinks cold 24h"),
    ("Silicone Kitchen Utensil Set",    "Home & Kitchen",    6.50, 19.99, "10-piece heat-resistant utensil set with holder"),
    ("French Press Coffee Maker 1L",    "Home & Kitchen",    7.00, 22.99, "Borosilicate glass with stainless steel filter"),
    ("Bamboo Cutting Board Set",        "Home & Kitchen",    8.00, 21.99, "Set of 3 boards with juice grooves and handles"),
    ("Ceramic Knife Set 4-Piece",       "Home & Kitchen",    9.00, 27.99, "Ultra-sharp ceramic blades with ergonomic handles"),
    ("Yoga Mat 6mm Non-Slip",           "Sports & Outdoors", 6.00, 19.99, "High-density TPE mat with carrying strap"),
    ("Resistance Bands Set",            "Sports & Outdoors", 3.50, 12.99, "5 bands with handles, door anchor, and carry bag"),
    ("Adjustable Jump Rope",            "Sports & Outdoors", 2.50,  9.99, "Speed rope with ball bearings and foam handles"),
    ("Compact Camping Hammock",         "Sports & Outdoors",10.00, 29.99, "Ripstop nylon hammock supports up to 150kg"),
    ("LED Headlamp Rechargeable",       "Sports & Outdoors", 5.50, 17.99, "300 lumens with red light mode and motion sensor"),
    ("Phone Case Shockproof",           "Accessories",       2.00,  9.99, "Military-grade drop protection with clear back"),
    ("Leather Minimalist Wallet",       "Accessories",       5.00, 18.99, "RFID-blocking slim wallet holds 8 cards"),
    ("Polarised Sunglasses UV400",      "Accessories",       4.00, 15.99, "Lightweight frame with scratch-resistant lenses"),
    ("Canvas Tote Bag Heavy Duty",      "Accessories",       3.50, 12.99, "Reinforced handles with interior zip pocket"),
]

SUPPLIER_DATA = [
    # (name, contact_person, email, phone)
    ("Shenzhen TechParts Co.",     "Li Wei",    "li.wei@sztechparts.cn",        "+86-755-8888-1001"),
    ("Guangzhou HomeGoods Ltd.",   "Chen Mei",  "chen.mei@gzhomegoods.cn",      "+86-20-3333-2002"),
    ("Dongguan Textiles Inc.",     "Zhang Hao", "zhang.hao@dgtextiles.cn",      "+86-769-5555-3003"),
    ("Yiwu Accessories Trading",   "Wang Fang", "wang.fang@ywaccessories.cn",   "+86-579-7777-4004"),
    ("Ningbo Sports Gear Co.",     "Huang Jun", "huang.jun@nbsportsgear.cn",    "+86-574-6666-5005"),
]

SUPPLIER_CATEGORY_MAP = {
    "Electronics":      "Shenzhen TechParts Co.",
    "Home & Kitchen":   "Guangzhou HomeGoods Ltd.",
    "Apparel":          "Dongguan Textiles Inc.",
    "Accessories":      "Yiwu Accessories Trading",
    "Sports & Outdoors":"Ningbo Sports Gear Co.",
}

PARTNER_DATA = [
    # (name, contact_person, email, phone, agreement_type)
    ("TechDeal Hub",    "Sarah Lim",    "sarah@techdealhub.sg",    "+65-9123-4567", "reseller"),
    ("FitLife Store",   "Ahmad Rahman", "ahmad@fitlifestore.my",   "+60-12-345-6789", "affiliate"),
    ("UrbanStyle Co.",  "Priya Nair",   "priya@urbanstyle.sg",     "+65-8234-5678", "collab"),
]

# partner id (1-indexed) → product categories they handle
PARTNER_CATEGORY_MAP = {
    1: ["Electronics", "Accessories"],
    2: ["Sports & Outdoors", "Apparel"],
    3: ["Apparel", "Accessories"],
}

CUSTOMER_NAMES = [
    "James Tan",        "Mei Ling Ong",      "Raj Kumar",        "Siti Aminah",
    "David Chen",       "Yuki Tanaka",        "Alex Wong",        "Nadia Hassan",
    "Kevin Loh",        "Fiona Teo",          "Muhammad Rizal",   "Grace Chong",
    "Benny Lim",        "Aisha Binte Yusof",  "Jason Lee",        "Hui Min Chua",
    "Daniel Goh",       "Priscilla Ng",       "Ryan Koh",         "Wen Hui Tan",
]

_PLATFORMS = ["WhatsApp", "Telegram", "Instagram DM", "Facebook Messenger", "Email"]
_CHANNELS = ["Shopee", "Lazada", "Carousell", "Website", "Instagram Shop"]
_ORDER_STATUSES = ["pending", "fulfilled", "cancelled"]


# ─── Row builders ─────────────────────────────────────────────────────────────

def generate_products() -> list[dict]:
    rows = []
    for i, (name, cat, cost, sell, desc) in enumerate(PRODUCT_CATALOG, start=1):
        rows.append({
            "id": i,
            "name": name,
            "description": desc,
            "selling_price": f"{sell:.2f}",
            "cost_price": f"{cost:.2f}",
            "stock_quantity": random.randint(10, 200),
            "category": cat,
            "link": f"https://store.example.com/products/{name.lower().replace(' ', '-')}",
        })
    return rows


def generate_customers() -> list[dict]:
    rows = []
    for i, name in enumerate(CUSTOMER_NAMES, start=1):
        rows.append({
            "id": i,
            "name": name,
            "email": f"{name.lower().replace(' ', '.')}@email.com",
            "phone": f"+65-{random.randint(8000, 9999)}-{random.randint(1000, 9999)}",
            "address": (
                f"Blk {random.randint(100, 999)} "
                f"#{random.randint(1, 20):02d}-{random.randint(1, 200):03d}, "
                f"Singapore {random.randint(100000, 999999)}"
            ),
            "platform": random.choice(_PLATFORMS),
        })
    return rows


def generate_orders(products: list[dict], customers: list[dict]) -> list[dict]:
    rows = []
    start_date = date(2025, 1, 1)
    end_date = date(2026, 3, 15)
    delta_days = (end_date - start_date).days

    for i in range(1, 121):
        product = random.choice(products)
        customer = random.choice(customers)
        qty = random.randint(1, 5)
        order_date = start_date + timedelta(days=random.randint(0, delta_days))
        rows.append({
            "id": i,
            "customer_id": customer["id"],
            "product_id": product["id"],
            "quantity": qty,
            "total_price": f"{float(product['selling_price']) * qty:.2f}",
            "order_date": order_date.isoformat(),
            "status": random.choice(_ORDER_STATUSES),
            "channel": random.choice(_CHANNELS),
        })
    return rows


def generate_suppliers() -> list[dict]:
    rows = []
    for i, (name, contact, email, phone) in enumerate(SUPPLIER_DATA, start=1):
        rows.append({
            "id": i,
            "name": name,
            "contact_person": contact,
            "email": email,
            "phone": phone,
        })
    return rows


def generate_supply_contracts(products: list[dict], suppliers: list[dict]) -> list[dict]:
    supplier_name_to_id = {s["name"]: s["id"] for s in suppliers}
    rows = []
    contract_id = 1

    for product in products:
        supplier_name = SUPPLIER_CATEGORY_MAP.get(product["category"])
        if not supplier_name:
            continue
        cost = float(product["cost_price"])
        rows.append({
            "id": contract_id,
            "supplier_id": supplier_name_to_id[supplier_name],
            "product_id": product["id"],
            "supply_price": f"{cost * random.uniform(0.85, 1.0):.2f}",
            "total_order_qty": random.choice([100, 200, 300, 500, 1000]),
            "lead_time_days": random.choice([7, 14, 21, 30, 45]),
            "contract_start": "2025-01-01",
            "contract_end": "2025-12-31",
            "is_active": True,
            "notes": "",
        })
        contract_id += 1
    return rows


def generate_partners() -> list[dict]:
    rows = []
    for i, (name, contact, email, phone, _) in enumerate(PARTNER_DATA, start=1):
        rows.append({
            "id": i,
            "name": name,
            "contact_person": contact,
            "email": email,
            "phone": phone,
        })
    return rows


def generate_partner_agreements(partners: list[dict]) -> list[dict]:
    rows = []
    for i, (partner, (_, _, _, _, atype)) in enumerate(zip(partners, PARTNER_DATA), start=1):
        rows.append({
            "id": i,
            "partner_id": partner["id"],
            "description": f"{atype.title()} agreement with {partner['name']}",
            "agreement_type": atype,
            "revenue_share_pct": f"{random.uniform(5, 20):.2f}",
            "start_date": "2025-01-01",
            "end_date": "2025-12-31",
            "is_active": True,
            "notes": "",
        })
    return rows


def generate_partner_products(partners: list[dict], products: list[dict]) -> list[dict]:
    rows = []
    pp_id = 1
    for partner in partners:
        categories = PARTNER_CATEGORY_MAP.get(partner["id"], [])
        linked = [p for p in products if p["category"] in categories]
        for product in random.sample(linked, min(5, len(linked))):
            rows.append({
                "id": pp_id,
                "partner_id": partner["id"],
                "product_id": product["id"],
                "agreement_id": partner["id"],
            })
            pp_id += 1
    return rows


# ─── CSV writer ───────────────────────────────────────────────────────────────

def _write_csv(filename: str, rows: list[dict]) -> None:
    if not rows:
        return
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    filepath = SEED_DIR / filename
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    print(f"  written {len(rows)} rows → {filepath}")


# ─── Main pipeline ────────────────────────────────────────────────────────────

def generate_all() -> None:
    random.seed(42)

    products = generate_products()
    customers = generate_customers()
    orders = generate_orders(products, customers)
    suppliers = generate_suppliers()
    supply_contracts = generate_supply_contracts(products, suppliers)
    partners = generate_partners()
    agreements = generate_partner_agreements(partners)
    partner_products = generate_partner_products(partners, products)

    _write_csv("products.csv", products)
    _write_csv("customers.csv", customers)
    _write_csv("orders.csv", orders)
    _write_csv("suppliers.csv", suppliers)
    _write_csv("supply_contracts.csv", supply_contracts)
    _write_csv("partners.csv", partners)
    _write_csv("partner_agreements.csv", agreements)
    _write_csv("partner_products.csv", partner_products)

    print("Done.")


if __name__ == "__main__":
    generate_all()
