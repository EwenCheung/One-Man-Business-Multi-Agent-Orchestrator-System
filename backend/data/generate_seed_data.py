"""
Seed Data Generator

Generates deterministic UUID-keyed CSV seed data for a one-man physical goods
e-commerce business based in Singapore.  Output files are written to
backend/data/seed/ and consumed by backend/db/load_seed_data.py.

All 15 CSVs required by the loader are produced:
    products, customers, suppliers, partners, orders,
    supply_contracts (→ SupplierProduct), partner_agreements,
    partner_products (→ PartnerProductRelation), external_identities,
    conversation_threads, messages, memory_update_proposals,
    held_replies, reply_review_records, pending_approvals

Usage:
    uv run python backend/data/generate_seed_data.py
"""

import csv
import json
import random
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).parent / "seed"
OWNER_ID = "4c116430-f683-4a8a-91f7-546fa8bc5d76"
REFERENCE_DATE = date(2026, 4, 1)
RNG = random.Random(20260403)


def seed_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "seed-data:" + ":".join(parts)))


# ─── Entity data ─────────────────────────────────────────────────────────────

# (name, category, cost_price, selling_price, description)
PRODUCT_CATALOG = [
    ("Wireless Bluetooth Earbuds",       "Electronics",       12.50, 29.99, "Compact earbuds with noise cancellation and 8-hour battery life"),
    ("USB-C Fast Charger 65W",           "Electronics",        8.00, 19.99, "GaN charger compatible with laptops, tablets, and phones"),
    ("Portable Power Bank 20000mAh",     "Electronics",       15.00, 34.99, "Slim power bank with dual USB-A and USB-C output"),
    ("Mechanical Keyboard RGB",          "Electronics",       22.00, 54.99, "Hot-swappable switches with per-key RGB lighting"),
    ("Wireless Gaming Mouse",            "Electronics",       10.00, 27.99, "Ergonomic design with adjustable DPI up to 16000"),
    ("Laptop Stand Aluminum",            "Electronics",        9.50, 24.99, "Adjustable height stand with ventilation slots"),
    ("4K Webcam with Mic",               "Electronics",       18.00, 44.99, "Auto-focus webcam with built-in noise-cancelling microphone"),
    ("Smart LED Desk Lamp",              "Electronics",       11.00, 29.99, "Touch-controlled lamp with 5 brightness levels and USB charging port"),
    ("Noise Cancelling Headphones",      "Electronics",       30.00, 74.99, "Over-ear headphones with ANC and 30-hour battery"),
    ("HDMI to USB-C Adapter",            "Electronics",        4.50, 14.99, "4K@60Hz adapter for MacBook and Windows laptops"),
    ("Men's Cotton T-Shirt",             "Apparel",            4.00, 14.99, "Premium cotton crew neck tee available in 8 colours"),
    ("Women's Running Leggings",         "Apparel",            7.00, 24.99, "High-waist moisture-wicking leggings with side pocket"),
    ("Unisex Zip Hoodie",                "Apparel",           12.00, 34.99, "Heavyweight fleece hoodie with metal YKK zipper"),
    ("Baseball Cap Embroidered",         "Apparel",            3.50, 12.99, "Adjustable snapback with embroidered logo"),
    ("Waterproof Hiking Jacket",         "Apparel",           25.00, 64.99, "Seam-sealed jacket with breathable membrane"),
    ("Bamboo Fiber Socks 6-Pack",        "Apparel",            3.00, 11.99, "Anti-bacterial bamboo socks with reinforced heel and toe"),
    ("Stainless Steel Water Bottle 750ml","Home & Kitchen",    5.00, 16.99, "Double-wall vacuum insulated keeps drinks cold 24h"),
    ("Silicone Kitchen Utensil Set",     "Home & Kitchen",     6.50, 19.99, "10-piece heat-resistant utensil set with holder"),
    ("French Press Coffee Maker 1L",     "Home & Kitchen",     7.00, 22.99, "Borosilicate glass with stainless steel filter"),
    ("Bamboo Cutting Board Set",         "Home & Kitchen",     8.00, 21.99, "Set of 3 boards with juice grooves and handles"),
    ("Ceramic Knife Set 4-Piece",        "Home & Kitchen",     9.00, 27.99, "Ultra-sharp ceramic blades with ergonomic handles"),
    ("Yoga Mat 6mm Non-Slip",            "Sports & Outdoors",  6.00, 19.99, "High-density TPE mat with carrying strap"),
    ("Resistance Bands Set",             "Sports & Outdoors",  3.50, 12.99, "5 bands with handles, door anchor, and carry bag"),
    ("Adjustable Jump Rope",             "Sports & Outdoors",  2.50,  9.99, "Speed rope with ball bearings and foam handles"),
    ("Compact Camping Hammock",          "Sports & Outdoors", 10.00, 29.99, "Ripstop nylon hammock supports up to 150kg"),
    ("LED Headlamp Rechargeable",        "Sports & Outdoors",  5.50, 17.99, "300 lumens with red light mode and motion sensor"),
    ("Phone Case Shockproof",            "Accessories",         2.00,  9.99, "Military-grade drop protection with clear back"),
    ("Leather Minimalist Wallet",        "Accessories",         5.00, 18.99, "RFID-blocking slim wallet holds 8 cards"),
    ("Polarised Sunglasses UV400",       "Accessories",         4.00, 15.99, "Lightweight frame with scratch-resistant lenses"),
    ("Canvas Tote Bag Heavy Duty",       "Accessories",         3.50, 12.99, "Reinforced handles with interior zip pocket"),
]

# (name, email, phone, company, preference, notes_extra, qty_range)
CUSTOMER_DATA = [
    ("James Tan",         "james.tan@email.com",         "+65-9123-4501", "TechGear SG",       "Prefers electronics bundles",                    "Platform: Shopee",            (2, 6)),
    ("Mei Ling Ong",      "mei.ling.ong@email.com",       "+65-9234-5602", "RetailPlus Pte Ltd","Bulk orders, net-30 preferred",                  "Platform: Email",             (10, 25)),
    ("Raj Kumar",         "raj.kumar@email.com",          "+65-9345-6703", None,                None,                                             "Platform: WhatsApp",          (1, 3)),
    ("Siti Aminah",       "siti.aminah@email.com",        "+65-9456-7804", "Aminah Boutique",   "Prefers apparel and accessories",                "Platform: Instagram DM",      (3, 8)),
    ("David Chen",        "david.chen@email.com",         "+65-9567-8905", "ChenTech Solutions","Requires invoice before shipment",               "Platform: Email",             (4, 12)),
    ("Yuki Tanaka",       "yuki.tanaka@email.com",        "+65-9678-9006", None,                None,                                             "Platform: Telegram",          (1, 4)),
    ("Alex Wong",         "alex.wong@email.com",          "+65-9789-0107", "Wong Supplies",     "Price-sensitive, flexible delivery",             "Platform: Lazada",            (5, 15)),
    ("Nadia Hassan",      "nadia.hassan@email.com",       "+65-9890-1208", None,                "Prefers home and kitchen category",              "Platform: Facebook Messenger",(1, 5)),
    ("Kevin Loh",         "kevin.loh@email.com",          "+65-9901-2309", "Loh Fitness",       "Regular sports equipment orders",                "Platform: WhatsApp",          (3, 10)),
    ("Fiona Teo",         "fiona.teo@email.com",          "+65-9012-3410", None,                None,                                             "Platform: Instagram DM",      (1, 3)),
    ("Muhammad Rizal",    "muhammad.rizal@email.com",     "+65-9123-4511", "Rizal Trading",     "Wholesale accessories buyer",                    "Platform: Email",             (8, 20)),
    ("Grace Chong",       "grace.chong@email.com",        "+65-9234-5612", None,                "Interested in apparel deals",                    "Platform: Shopee",            (2, 6)),
    ("Benny Lim",         "benny.lim@email.com",          "+65-9345-6713", "BL Electronics",   "Electronics reseller, needs volume pricing",     "Platform: Email",             (10, 30)),
    ("Aisha Binte Yusof", "aisha.yusof@email.com",        "+65-9456-7814", None,                None,                                             "Platform: WhatsApp",          (1, 4)),
    ("Jason Lee",         "jason.lee@email.com",          "+65-9567-8915", "JL Sports",         "Sports and outdoors bulk buyer",                 "Platform: Lazada",            (5, 12)),
    ("Hui Min Chua",      "hui.min.chua@email.com",       "+65-9678-9016", None,                "Prefers bundled accessories",                    "Platform: Carousell",         (1, 5)),
    ("Daniel Goh",        "daniel.goh@email.com",         "+65-9789-0117", "Goh Home Concepts", "Home and kitchen category focus",                "Platform: Facebook Messenger",(4, 10)),
    ("Priscilla Ng",      "priscilla.ng@email.com",       "+65-9890-1218", None,                None,                                             "Platform: Instagram DM",      (1, 3)),
    ("Ryan Koh",          "ryan.koh@email.com",           "+65-9901-2319", "Koh Active Wear",   "Apparel and sports orders for retail",           "Platform: Email",             (6, 18)),
    ("Wen Hui Tan",       "wen.hui.tan@email.com",        "+65-9012-3420", None,                None,                                             "Platform: WhatsApp",          (1, 4)),
]

# (name, contact_person, email, phone, category)
SUPPLIER_DATA = [
    ("Shenzhen TechParts Co.",    "Li Wei",    "li.wei@sztechparts.cn",      "+86-755-8888-1001", "Electronics"),
    ("Guangzhou HomeGoods Ltd.",  "Chen Mei",  "chen.mei@gzhomegoods.cn",    "+86-20-3333-2002",  "Home & Kitchen"),
    ("Dongguan Textiles Inc.",    "Zhang Hao", "zhang.hao@dgtextiles.cn",    "+86-769-5555-3003", "Apparel"),
    ("Yiwu Accessories Trading",  "Wang Fang", "wang.fang@ywaccessories.cn", "+86-579-7777-4004", "Accessories"),
    ("Ningbo Sports Gear Co.",    "Huang Jun", "huang.jun@nbsportsgear.cn",  "+86-574-6666-5005", "Sports & Outdoors"),
]

SUPPLIER_CATEGORY_MAP: dict[str, str] = {
    "Electronics":      "Shenzhen TechParts Co.",
    "Home & Kitchen":   "Guangzhou HomeGoods Ltd.",
    "Apparel":          "Dongguan Textiles Inc.",
    "Accessories":      "Yiwu Accessories Trading",
    "Sports & Outdoors":"Ningbo Sports Gear Co.",
}

# (name, contact_person, email, phone, partner_type, agreement_type, revenue_share_pct)
PARTNER_DATA = [
    ("TechDeal Hub",   "Sarah Lim",    "sarah@techdealhub.sg",  "+65-9123-4567", "reseller",  "reseller",  Decimal("10.00")),
    ("FitLife Store",  "Ahmad Rahman", "ahmad@fitlifestore.my", "+60-12-345-6789","affiliate", "affiliate", Decimal("8.50")),
    ("UrbanStyle Co.", "Priya Nair",   "priya@urbanstyle.sg",   "+65-8234-5678", "Media",     "collab",    Decimal("12.00")),
]

# partner index (0-based) → product categories they carry
PARTNER_CATEGORY_MAP: dict[int, list[str]] = {
    0: ["Electronics", "Accessories"],
    1: ["Sports & Outdoors", "Apparel"],
    2: ["Apparel", "Accessories"],
}

_CHANNELS = ["Shopee", "Lazada", "Carousell", "Website", "Instagram Shop"]
_ORDER_STATUSES = ["pending", "fulfilled", "cancelled"]


# ─── Generators ──────────────────────────────────────────────────────────────

def generate_products() -> list[dict[str, Any]]:
    rows = []
    for name, category, cost, sell, desc in PRODUCT_CATALOG:
        rows.append({
            "id":            seed_uuid("product", name),
            "owner_id":      OWNER_ID,
            "name":          name,
            "description":   desc,
            "selling_price": f"{sell:.2f}",
            "cost_price":    f"{cost:.2f}",
            "stock_number":  RNG.randint(20, 300),
            "product_link":  f"https://store.example.com/products/{name.lower().replace(' ', '-')}",
            "category":      category,
        })
    return rows


def generate_customers() -> list[dict[str, Any]]:
    rows = []
    for idx, (name, email, phone, company, preference, notes_extra, qty_range) in enumerate(CUSTOMER_DATA):
        last_contact = REFERENCE_DATE - timedelta(days=(idx + 1) * 7)
        rows.append({
            "id":           seed_uuid("customer", email),
            "owner_id":     OWNER_ID,
            "name":         name,
            "email":        email,
            "phone":        phone,
            "company":      company or "",
            "status":       "active",
            "preference":   preference or "",
            "notes":        notes_extra,
            "last_contact": last_contact.isoformat(),
            # internal — stripped before CSV write
            "_qty_range":   qty_range,
        })
    return rows


def generate_suppliers() -> list[dict[str, Any]]:
    rows = []
    for name, contact, email, phone, category in SUPPLIER_DATA:
        rows.append({
            "id":             seed_uuid("supplier", email),
            "owner_id":       OWNER_ID,
            "name":           name,
            "email":          email,
            "phone":          phone,
            "category":       category,
            "contract_notes": f"Primary contact: {contact}. {category} procurement supplier.",
            "status":         "active",
        })
    return rows


def generate_partners() -> list[dict[str, Any]]:
    rows = []
    for name, contact, email, phone, partner_type, agreement_type, rev_share in PARTNER_DATA:
        rows.append({
            "id":           seed_uuid("partner", email),
            "owner_id":     OWNER_ID,
            "name":         name,
            "email":        email,
            "phone":        phone,
            "partner_type": partner_type,
            "notes":        f"Contact: {contact}. Agreement type: {agreement_type}.",
            "status":       "active",
            # internal
            "_agreement_type":    agreement_type,
            "_revenue_share_pct": str(rev_share),
        })
    return rows


def generate_orders(customers: list[dict], products: list[dict]) -> list[dict[str, Any]]:
    products_by_category: dict[str, list[dict]] = {}
    for p in products:
        products_by_category.setdefault(p["category"], []).append(p)

    rows = []
    start_date = date(2025, 1, 1)
    end_date = REFERENCE_DATE - timedelta(days=1)
    delta_days = (end_date - start_date).days

    for order_idx in range(1, 121):
        customer = RNG.choice(customers)
        product = RNG.choice(products)
        qty_min, qty_max = customer["_qty_range"]
        qty = RNG.randint(qty_min, qty_max)
        order_date = start_date + timedelta(days=RNG.randint(0, delta_days))
        rows.append({
            "id":          seed_uuid("order", str(order_idx), customer["id"], product["id"]),
            "owner_id":    OWNER_ID,
            "customer_id": customer["id"],
            "product_id":  product["id"],
            "quantity":    qty,
            "total_price": f"{float(product['selling_price']) * qty:.2f}",
            "order_date":  order_date.isoformat(),
            "status":      RNG.choices(_ORDER_STATUSES, weights=[2, 6, 1], k=1)[0],
            "channel":     RNG.choice(_CHANNELS),
        })
    return rows


def generate_supply_contracts(suppliers: list[dict], products: list[dict]) -> list[dict[str, Any]]:
    supplier_by_name = {s["name"]: s for s in suppliers}
    rows = []
    for product in products:
        supplier_name = SUPPLIER_CATEGORY_MAP.get(product["category"])
        if not supplier_name:
            continue
        supplier = supplier_by_name[supplier_name]
        cost = float(product["cost_price"])
        contract_start = REFERENCE_DATE - timedelta(days=RNG.randint(120, 420))
        contract_end = contract_start + timedelta(days=RNG.randint(365, 730))
        rows.append({
            "id":             seed_uuid("supply-contract", supplier["id"], product["id"]),
            "owner_id":       OWNER_ID,
            "supplier_id":    supplier["id"],
            "product_id":     product["id"],
            "supply_price":   f"{cost * RNG.uniform(0.82, 0.95):.2f}",
            "stock_we_buy":   RNG.randint(100, 800),
            "contract":       f"{supplier['name']} supply agreement for {product['name']}",
            "lead_time_days": RNG.choice([7, 14, 21, 30, 45]),
            "contract_start": contract_start.isoformat(),
            "contract_end":   contract_end.isoformat(),
            "is_active":      "true",
            "notes":          f"Category: {product['category']}. Standard procurement terms apply.",
        })
    return rows


def generate_partner_agreements(partners: list[dict]) -> list[dict[str, Any]]:
    rows = []
    for partner in partners:
        start_date = REFERENCE_DATE - timedelta(days=RNG.randint(90, 300))
        end_date = start_date + timedelta(days=RNG.randint(365, 730))
        rows.append({
            "id":                seed_uuid("partner-agreement", partner["id"]),
            "owner_id":          OWNER_ID,
            "partner_id":        partner["id"],
            "description":       f"{partner['name']} {partner['_agreement_type']} agreement covering channel distribution and campaign KPIs",
            "agreement_type":    partner["_agreement_type"],
            "revenue_share_pct": partner["_revenue_share_pct"],
            "start_date":        start_date.isoformat(),
            "end_date":          end_date.isoformat(),
            "is_active":         "true",
            "notes":             "Monthly performance sync and quarterly optimisation review.",
        })
    return rows


def generate_partner_products(
    partners: list[dict],
    products: list[dict],
    agreements: list[dict],
) -> list[dict[str, Any]]:
    agreement_by_partner_id = {a["partner_id"]: a for a in agreements}
    products_by_category: dict[str, list[dict]] = {}
    for p in products:
        products_by_category.setdefault(p["category"], []).append(p)

    rows = []
    for idx, partner in enumerate(partners):
        agreement = agreement_by_partner_id.get(partner["id"])
        for category in PARTNER_CATEGORY_MAP.get(idx, []):
            pool = products_by_category.get(category, [])
            for product in RNG.sample(pool, min(4, len(pool))):
                rows.append({
                    "id":           seed_uuid("partner-product", partner["id"], product["id"]),
                    "owner_id":     OWNER_ID,
                    "partner_id":   partner["id"],
                    "product_id":   product["id"],
                    "agreement_id": agreement["id"] if agreement else "",
                })
    return rows


def generate_external_identities(
    customers: list[dict],
    suppliers: list[dict],
    partners: list[dict],
) -> list[dict[str, Any]]:
    rows = []
    for role, entities in (("customer", customers), ("supplier", suppliers), ("partner", partners)):
        for entity in entities:
            email = entity.get("email", "")
            if not email:
                continue
            rows.append({
                "id":                seed_uuid("external-identity", role, entity["id"]),
                "owner_id":          OWNER_ID,
                "external_id":       email.strip().lower(),
                "external_type":     "email",
                "entity_role":       role,
                "entity_id":         entity["id"],
                "is_primary":        "true",
                "identity_metadata": json.dumps(
                    {"source": "seed", "entity_name": entity["name"]}, separators=(",", ":")
                ),
            })
    return rows


def generate_conversation_threads(
    customers: list[dict],
    suppliers: list[dict],
    partners: list[dict],
) -> list[dict[str, Any]]:
    seed_pool = [
        ("customer", customers[0],  "email", "Order ETA and restock inquiry"),
        ("customer", customers[1],  "email", "Bulk order change request"),
        ("supplier", suppliers[0],  "email", "Lead time adjustment discussion"),
        ("partner",  partners[0],   "email", "Campaign performance follow-up"),
        ("customer", customers[4],  "email", "Approval needed for high-value quote"),
    ]
    rows = []
    for idx, (role, entity, channel, title) in enumerate(seed_pool, start=1):
        rows.append({
            "id":                seed_uuid("conversation-thread", str(idx), entity["id"]),
            "owner_id":          OWNER_ID,
            "thread_type":       "external_sender",
            "title":             title,
            "sender_external_id":entity["email"].strip().lower(),
            "sender_name":       entity["name"],
            "sender_role":       role,
            "sender_channel":    channel,
        })
    return rows


def generate_messages(threads: list[dict]) -> list[dict[str, Any]]:
    templates = [
        ("inbound",  "Could you confirm availability and delivery timing for this week?"),
        ("outbound", "Yes, we can fulfil from current stock and share shipment confirmation shortly."),
    ]
    rows = []
    for thread in threads:
        for idx, (direction, content) in enumerate(templates, start=1):
            rows.append({
                "id":                     seed_uuid("message", thread["id"], direction, str(idx)),
                "owner_id":               OWNER_ID,
                "conversation_thread_id": thread["id"],
                "sender_id":              thread["sender_external_id"],
                "sender_name":            thread["sender_name"],
                "sender_role":            thread["sender_role"],
                "direction":              direction,
                "content":                content,
            })

    approval_thread = threads[-1]
    rows.append({
        "id":                     seed_uuid("message", approval_thread["id"], "approved-reply"),
        "owner_id":               OWNER_ID,
        "conversation_thread_id": approval_thread["id"],
        "sender_id":              approval_thread["sender_external_id"],
        "sender_name":            approval_thread["sender_name"],
        "sender_role":            approval_thread["sender_role"],
        "direction":              "outbound",
        "content":                "We can proceed once procurement approval is finalised. I will send the formal quote next.",
    })
    return rows


def generate_memory_update_proposals(customers: list[dict]) -> list[dict[str, Any]]:
    pending_customer = customers[1]   # Mei Ling Ong — bulk buyer
    approved_customer = customers[3]  # Siti Aminah — boutique
    return [
        {
            "id":               seed_uuid("memory-proposal", "pending", pending_customer["id"]),
            "owner_id":         OWNER_ID,
            "target_table":     "customers",
            "target_id":        pending_customer["id"],
            "proposed_content": json.dumps(
                [{
                    "sender_id":   pending_customer["email"],
                    "sender_name": pending_customer["name"],
                    "sender_role": "customer",
                    "memory_type": "preference",
                    "content":     "RetailPlus requested pallet-level packaging and Friday-only dock delivery.",
                    "summary":     "RetailPlus prefers palletised Friday deliveries",
                    "tags":        ["logistics", "bulk-order"],
                    "importance":  0.82,
                }],
                separators=(",", ":"),
            ),
            "reason":     "Detected stable logistics preference from recent thread",
            "risk_level": "medium",
            "status":     "pending",
        },
        {
            "id":               seed_uuid("memory-proposal", "approved", approved_customer["id"]),
            "owner_id":         OWNER_ID,
            "target_table":     "customers",
            "target_id":        approved_customer["id"],
            "proposed_content": json.dumps(
                [{
                    "sender_id":   approved_customer["email"],
                    "sender_name": approved_customer["name"],
                    "sender_role": "customer",
                    "memory_type": "billing",
                    "content":     "Aminah Boutique accepted prepaid terms for first two replenishment cycles.",
                    "summary":     "Aminah Boutique temporary prepaid billing window",
                    "tags":        ["finance", "terms"],
                    "importance":  0.65,
                }],
                separators=(",", ":"),
            ),
            "reason":     "Owner previously approved this billing update",
            "risk_level": "low",
            "status":     "approved",
        },
    ]


def generate_held_replies(threads: list[dict]) -> list[dict[str, Any]]:
    risky_thread = threads[1]       # bulk order change
    high_risk_thread = threads[4]   # approval quote
    return [
        {
            "id":              seed_uuid("held-reply", "pending", risky_thread["id"]),
            "owner_id":        OWNER_ID,
            "thread_id":       risky_thread["id"],
            "sender_id":       risky_thread["sender_external_id"],
            "sender_name":     risky_thread["sender_name"],
            "sender_role":     risky_thread["sender_role"],
            "reply_text":      "We can authorise a 25% one-time discount and bypass standard credit checks.",
            "risk_level":      "high",
            "risk_flags":      json.dumps(["pricing-policy-breach", "credit-policy-breach"], separators=(",", ":")),
            "status":          "pending",
            "reviewer_notes":  "",
        },
        {
            "id":              seed_uuid("held-reply", "approved", high_risk_thread["id"]),
            "owner_id":        OWNER_ID,
            "thread_id":       high_risk_thread["id"],
            "sender_id":       high_risk_thread["sender_external_id"],
            "sender_name":     high_risk_thread["sender_name"],
            "sender_role":     high_risk_thread["sender_role"],
            "reply_text":      "We can provide a preliminary quote after legal review confirms partner terms.",
            "risk_level":      "medium",
            "risk_flags":      json.dumps(["legal-review-required"], separators=(",", ":")),
            "status":          "approved",
            "reviewer_notes":  "Approved with legal gate.",
        },
    ]


def generate_reply_review_records(
    held_replies: list[dict],
    threads: list[dict],
    messages: list[dict],
) -> list[dict[str, Any]]:
    thread_by_id = {t["id"]: t for t in threads}
    approved_message = next(
        m for m in messages
        if m["id"] == seed_uuid("message", threads[4]["id"], "approved-reply")
    )
    rows = []
    for held in held_replies:
        thread = thread_by_id.get(held["thread_id"])
        sender_name = thread["sender_name"] if thread else held["sender_name"]
        pending = held["status"] == "pending"
        rows.append({
            "id":                   seed_uuid("reply-review", held["id"]),
            "owner_id":             OWNER_ID,
            "trace_id":             seed_uuid("trace", held["id"]),
            "thread_id":            held["thread_id"],
            "sender_id":            held["sender_id"],
            "sender_name":          held["sender_name"],
            "sender_role":          held["sender_role"],
            "raw_message":          f"{sender_name} requested policy exception for order terms.",
            "reply_text":           held["reply_text"],
            "risk_level":           held["risk_level"],
            "risk_flags":           held["risk_flags"],
            "approval_rule_flags":  json.dumps(["human-approval-required"], separators=(",", ":")),
            "requires_approval":    "true",
            "final_decision":       "held_pending_review" if pending else "approved_and_sent",
            "review_label":         "needs-owner-review" if pending else "approved",
            "reviewer_reason":      "Pending owner confirmation" if pending else "Approved with constraints",
            "held_reply_id":        held["id"],
            "message_id":           "" if pending else approved_message["id"],
        })
    return rows


def generate_pending_approvals(
    memory_proposals: list[dict],
    held_replies: list[dict],
) -> list[dict[str, Any]]:
    pending_memory = next(p for p in memory_proposals if p["status"] == "pending")
    rows = [
        {
            "id":            seed_uuid("pending-approval", "memory", pending_memory["id"]),
            "owner_id":      OWNER_ID,
            "title":         "Memory update requires review",
            "sender":        "Memory Agent",
            "preview":       "RetailPlus requested pallet-level packaging and Friday-only dock delivery.",
            "proposal_type": "memory-update",
            "risk_level":    pending_memory["risk_level"],
            "status":        "pending",
            "proposal_id":   pending_memory["id"],
            "held_reply_id": "",
        }
    ]
    for held in held_replies:
        if held["status"] != "pending":
            continue
        rows.append({
            "id":            seed_uuid("pending-approval", "reply", held["id"]),
            "owner_id":      OWNER_ID,
            "title":         f"Reply requires approval ({held['risk_level']} risk)",
            "sender":        held["sender_name"],
            "preview":       held["reply_text"][:200],
            "proposal_type": "reply-approval",
            "risk_level":    held["risk_level"],
            "status":        "pending",
            "proposal_id":   "",
            "held_reply_id": held["id"],
        })
    return rows


# ─── CSV writer ───────────────────────────────────────────────────────────────

def _strip_internal(rows: list[dict]) -> list[dict]:
    return [{k: v for k, v in row.items() if not k.startswith("_")} for row in rows]


def _write_csv(filename: str, rows: list[dict], fieldnames: list[str]) -> None:
    SEED_DIR.mkdir(parents=True, exist_ok=True)
    filepath = SEED_DIR / filename
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  {len(rows):>4} rows → {filename}")


# ─── Main pipeline ────────────────────────────────────────────────────────────

def generate() -> None:
    products   = generate_products()
    customers  = generate_customers()
    suppliers  = generate_suppliers()
    partners   = generate_partners()

    orders             = generate_orders(customers, products)
    supply_contracts   = generate_supply_contracts(suppliers, products)
    partner_agreements = generate_partner_agreements(partners)
    partner_products   = generate_partner_products(partners, products, partner_agreements)

    external_identities      = generate_external_identities(customers, suppliers, partners)
    conversation_threads     = generate_conversation_threads(customers, suppliers, partners)
    messages                 = generate_messages(conversation_threads)
    memory_update_proposals  = generate_memory_update_proposals(customers)
    held_replies             = generate_held_replies(conversation_threads)
    reply_review_records     = generate_reply_review_records(held_replies, conversation_threads, messages)
    pending_approvals        = generate_pending_approvals(memory_update_proposals, held_replies)

    _write_csv("products.csv", _strip_internal(products), [
        "id", "owner_id", "name", "description", "selling_price",
        "cost_price", "stock_number", "product_link", "category",
    ])
    _write_csv("customers.csv", _strip_internal(customers), [
        "id", "owner_id", "name", "email", "phone",
        "company", "status", "preference", "notes", "last_contact",
    ])
    _write_csv("suppliers.csv", _strip_internal(suppliers), [
        "id", "owner_id", "name", "email", "phone",
        "category", "contract_notes", "status",
    ])
    _write_csv("partners.csv", _strip_internal(partners), [
        "id", "owner_id", "name", "email", "phone", "partner_type", "notes", "status",
    ])
    _write_csv("orders.csv", orders, [
        "id", "owner_id", "customer_id", "product_id",
        "quantity", "total_price", "order_date", "status", "channel",
    ])
    _write_csv("supply_contracts.csv", supply_contracts, [
        "id", "owner_id", "supplier_id", "product_id", "supply_price",
        "stock_we_buy", "contract", "lead_time_days",
        "contract_start", "contract_end", "is_active", "notes",
    ])
    _write_csv("partner_agreements.csv", _strip_internal(partner_agreements), [
        "id", "owner_id", "partner_id", "description", "agreement_type",
        "revenue_share_pct", "start_date", "end_date", "is_active", "notes",
    ])
    _write_csv("partner_products.csv", partner_products, [
        "id", "owner_id", "partner_id", "product_id", "agreement_id",
    ])
    _write_csv("external_identities.csv", external_identities, [
        "id", "owner_id", "external_id", "external_type",
        "entity_role", "entity_id", "is_primary", "identity_metadata",
    ])
    _write_csv("conversation_threads.csv", conversation_threads, [
        "id", "owner_id", "thread_type", "title",
        "sender_external_id", "sender_name", "sender_role", "sender_channel",
    ])
    _write_csv("messages.csv", messages, [
        "id", "owner_id", "conversation_thread_id",
        "sender_id", "sender_name", "sender_role", "direction", "content",
    ])
    _write_csv("memory_update_proposals.csv", memory_update_proposals, [
        "id", "owner_id", "target_table", "target_id",
        "proposed_content", "reason", "risk_level", "status",
    ])
    _write_csv("held_replies.csv", held_replies, [
        "id", "owner_id", "thread_id", "sender_id", "sender_name", "sender_role",
        "reply_text", "risk_level", "risk_flags", "status", "reviewer_notes",
    ])
    _write_csv("reply_review_records.csv", reply_review_records, [
        "id", "owner_id", "trace_id", "thread_id", "sender_id", "sender_name",
        "sender_role", "raw_message", "reply_text", "risk_level", "risk_flags",
        "approval_rule_flags", "requires_approval", "final_decision",
        "review_label", "reviewer_reason", "held_reply_id", "message_id",
    ])
    _write_csv("pending_approvals.csv", pending_approvals, [
        "id", "owner_id", "title", "sender", "preview", "proposal_type",
        "risk_level", "status", "proposal_id", "held_reply_id",
    ])

    print("Seed data generation complete.")


if __name__ == "__main__":
    generate()
