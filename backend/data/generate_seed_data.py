"""Canonical lecture demo seed generator.

Generates deterministic owner-scoped CSV seed data under ``backend/data/seed``.
Expected owner records are read from ``owners.json`` created by
``backend/db/reset_and_seed_supabase.py``.
"""

from __future__ import annotations

import csv
import json
import uuid
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

SEED_DIR = Path(__file__).parent / "seed"
OWNERS_FILE = SEED_DIR / "owners.json"
REFERENCE_DATE = date(2026, 4, 1)
ROLE_SUFFIXES = ("A", "B", "C")

OWNER_SCENARIOS: dict[str, dict[str, Any]] = {
    "owner1": {
        "products": [
            (
                "Ergo Wireless Mouse",
                "Workspace Gear",
                "Reliable ergonomic mouse for all-day office use",
                Decimal("32.90"),
                Decimal("18.40"),
                42,
            ),
            (
                "7-in-1 USB-C Hub",
                "Workspace Gear",
                "USB-C hub bundled for laptop teams and hybrid workers",
                Decimal("44.00"),
                Decimal("26.50"),
                34,
            ),
            (
                "Mechanical Keyboard Bundle",
                "Workspace Gear",
                "Keyboard bundle for office setup refresh projects",
                Decimal("88.00"),
                Decimal("54.90"),
                22,
            ),
            (
                "Adjustable Laptop Stand",
                "Desk Setup",
                "Aluminum laptop stand for hot-desk and meeting rooms",
                Decimal("35.50"),
                Decimal("20.10"),
                30,
            ),
            (
                "Noise-Reducing Headset",
                "Workspace Gear",
                "Headset for customer service and remote collaboration teams",
                Decimal("64.00"),
                Decimal("39.20"),
                26,
            ),
            (
                "Starter Desk Setup Kit",
                "Bundles",
                "Mouse, hub, stand, and cable kit for new staff onboarding",
                Decimal("119.00"),
                Decimal("73.00"),
                14,
            ),
        ],
        "display_names": {
            "customer": {
                "A": "Crestview Academy Procurement",
                "B": "Harbor Ops Team",
                "C": "BrightPath Co-Working",
            },
            "supplier": {
                "A": "Shenzhen Device Works",
                "B": "PackRight Logistics",
                "C": "Metro Cable Components",
            },
            "partner": {
                "A": "Office Fitout Alliance",
                "B": "Team Productivity Marketplace",
                "C": "Hybrid Work Campaign Studio",
            },
            "investor": {
                "A": "SMB Commerce Angels",
                "B": "Efficiency Growth Fund",
                "C": "Regional Retail Ventures",
            },
        },
        "customer_preference": "Prefers concise quotations with stock status, delivery ETA, and bundle options in one reply",
        "customer_note": "Often places repeat team orders after a quick approval round with finance.",
        "supplier_category": {
            "A": "Input Devices",
            "B": "Packaging & Fulfilment",
            "C": "Connectivity Components",
        },
        "supplier_contract_note": {
            "A": "Primary source for mice, keyboards, and headset stock.",
            "B": "Handles packing material and overflow fulfilment.",
            "C": "Covers accessory and cable replenishment.",
        },
        "partner_types": {"A": "fitout-referral", "B": "reseller", "C": "campaign"},
        "partner_note": "Drives B2B lead flow when stock availability and bundle pricing are updated weekly.",
        "investor_focus": {
            "A": "Repeat order growth, bundle margin, and fulfilment reliability",
            "B": "Procurement efficiency and stock turns",
            "C": "Channel expansion with office and school accounts",
        },
        "investor_note": "Wants clean monthly margin view split by bundles and replenishment risk.",
        "message_inbound": {
            "customer": "Can you confirm stock, bundle price, and delivery timing for our next workspace order?",
            "supplier": "Please confirm your next shipment window for keyboards and mice before we commit the PO.",
            "partner": "Can you send this week's bundle highlights and stock-safe offers for our campaign push?",
            "investor": "Share the latest repeat-order trend and whether stock constraints will slow April growth.",
        },
        "message_outbound": {
            "customer": "Yes — I will send stock-safe bundle options, firm ETA, and final terms in one update.",
            "supplier": "Understood. I will align PO timing to your confirmed lead time and flag any coverage gap.",
            "partner": "Yes — I will send the current bundle shortlist, stock-safe offers, and simple campaign angles today.",
            "investor": "Yes — I will share repeat-order trend, margin view, and any stock risk affecting April delivery.",
        },
    },
    "owner2": {
        "products": [
            (
                "Cold Brew Bottle Crate",
                "Beverage Service",
                "Bottle crate set for café cold brew and takeaway prep",
                Decimal("26.00"),
                Decimal("14.20"),
                48,
            ),
            (
                "Compostable Paper Cup Pack",
                "Packaging",
                "Wholesale compostable cup pack for café takeaway service",
                Decimal("18.50"),
                Decimal("9.60"),
                76,
            ),
            (
                "Custom Sticker Label Roll",
                "Packaging",
                "Branding label rolls for takeaway cups and pastry boxes",
                Decimal("21.90"),
                Decimal("11.80"),
                54,
            ),
            (
                "Barista Syrup Dispenser",
                "Beverage Service",
                "Countertop dispenser for high-volume beverage stations",
                Decimal("33.00"),
                Decimal("18.00"),
                25,
            ),
            (
                "Takeaway Carrier Tray",
                "Packaging",
                "Durable tray for multi-cup takeaway orders",
                Decimal("15.20"),
                Decimal("7.40"),
                92,
            ),
            (
                "Seasonal Launch Pack",
                "Bundles",
                "Cup pack, labels, carriers, and display add-ons for new menu launches",
                Decimal("84.00"),
                Decimal("47.50"),
                18,
            ),
        ],
        "display_names": {
            "customer": {
                "A": "Daily Dose Café Group",
                "B": "Morning Roast Kiosk",
                "C": "Harbor Bakeshop",
            },
            "supplier": {
                "A": "EcoPack Manufacturing",
                "B": "BeanLine Equipment Supply",
                "C": "QuickPrint Labels Co",
            },
            "partner": {
                "A": "Foodie District Guide",
                "B": "Weekend Market Events",
                "C": "City Café Campaign Lab",
            },
            "investor": {
                "A": "Hospitality Growth Syndicate",
                "B": "Consumer Ops Capital",
                "C": "Urban Food Ventures",
            },
        },
        "customer_preference": "Prefers reorder-ready replies with MOQ, delivery day, and branding options clearly stated",
        "customer_note": "Frequently reorders when seasonal launches are packaged into one simple offer.",
        "supplier_category": {
            "A": "Eco Packaging",
            "B": "Drinkware Equipment",
            "C": "Print & Labels",
        },
        "supplier_contract_note": {
            "A": "Core supplier for cups, trays, and compostable packaging.",
            "B": "Supports brew-tool and countertop accessory restocks.",
            "C": "Handles custom print turnaround for launch windows.",
        },
        "partner_types": {"A": "community-referral", "B": "event", "C": "campaign"},
        "partner_note": "Performs best when launch packs and seasonal offers are supplied with ready-made messaging.",
        "investor_focus": {
            "A": "Wholesale reorder growth, gross margin, and packaging mix",
            "B": "Cash conversion and stock discipline",
            "C": "Expansion readiness across café chains and events",
        },
        "investor_note": "Wants clearer visibility into repeat wholesale demand and seasonal campaign ROI.",
        "message_inbound": {
            "customer": "Can you confirm the reorder price, delivery slot, and branding options for next week's café launch?",
            "supplier": "Please confirm cup stock and print lead time before we open the next wholesale promo.",
            "partner": "Can you send the seasonal launch pack details and best-performing talking points for our audience?",
            "investor": "Share the latest wholesale reorder trend and whether packaging margins are holding this month.",
        },
        "message_outbound": {
            "customer": "Yes — I will send MOQ, delivery day, branding options, and the clean reorder summary in one message.",
            "supplier": "Got it. I will verify stock, print lead time, and any promo risk before we lock the next run.",
            "partner": "Yes — I will send the seasonal launch pack, campaign angle, and stock-safe offer list today.",
            "investor": "Yes — I will share reorder trend, margin health, and any packaging risk affecting this month's plan.",
        },
    },
}


def seed_uuid(*parts: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "seed-data:" + ":".join(parts)))


def owner_index(owner: dict[str, str]) -> str:
    return owner["label"].replace("owner", "")


def owner_scenario(owner: dict[str, str]) -> dict[str, Any]:
    return OWNER_SCENARIOS[owner["label"]]


def load_owners() -> list[dict[str, str]]:
    if not OWNERS_FILE.exists():
        raise FileNotFoundError(f"{OWNERS_FILE} not found. Run reset_and_seed_supabase first.")
    owners = json.loads(OWNERS_FILE.read_text())
    if not owners:
        raise ValueError("owners.json is empty")
    return owners


def write_csv(filename: str, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    filepath = SEED_DIR / filename
    filepath.parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "w", newline="", encoding="utf-8") as file_obj:
        writer = csv.DictWriter(file_obj, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Generated {len(rows)} rows -> {filename}")


def _participant(owner: dict[str, str], role: str, suffix: str) -> dict[str, str]:
    idx = owner_index(owner)
    scenario = owner_scenario(owner)
    phone_prefix = {"customer": "1555", "supplier": "1666", "partner": "1777", "investor": "1888"}[
        role
    ]
    return {
        "id": seed_uuid(role, owner["label"], suffix),
        "owner_id": owner["id"],
        "idx": idx,
        "suffix": suffix,
        "name": scenario["display_names"][role][suffix],
        "email": f"{role}{idx}{suffix}@gmail.com",
        "phone": f"+{phone_prefix}00{idx}{ord(suffix) - ord('A') + 1:02d}",
    }


def _group_by_owner(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["owner_id"], []).append(row)
    return grouped


def _email_suffix(email: str) -> str:
    local = email.split("@")[0]
    return local[-1].upper()


def _owner_label_from_seed_email(email: str) -> str:
    local = email.split("@")[0]
    owner_idx = local[-2]
    return f"owner{owner_idx}"


def generate_products(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        scenario = owner_scenario(owner)
        for name, category, description, sell, cost, stock in scenario["products"]:
            rows.append(
                {
                    "id": seed_uuid("product", owner["label"], name),
                    "owner_id": owner["id"],
                    "name": name,
                    "description": description,
                    "selling_price": str(sell),
                    "cost_price": str(cost),
                    "stock_number": stock,
                    "product_link": f"https://example.com/{owner['label']}/{name.lower().replace(' ', '-')}",
                    "category": category,
                }
            )
    return rows


def generate_customers(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        scenario = owner_scenario(owner)
        for suffix in ROLE_SUFFIXES:
            base = _participant(owner, "customer", suffix)
            rows.append(
                {
                    "id": base["id"],
                    "owner_id": base["owner_id"],
                    "name": base["name"],
                    "email": base["email"],
                    "phone": base["phone"],
                    "company": f"{base['name']} Pte Ltd",
                    "status": "active",
                    "preference": scenario["customer_preference"],
                    "notes": scenario["customer_note"],
                    "telegram_user_id": "",
                    "telegram_username": f"customer{base['idx']}{suffix}".lower(),
                    "telegram_chat_id": "",
                    "last_contact": (
                        REFERENCE_DATE - timedelta(days=(ord(suffix) - ord("A") + 1))
                    ).isoformat(),
                }
            )
    return rows


def generate_suppliers(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        scenario = owner_scenario(owner)
        for suffix in ROLE_SUFFIXES:
            base = _participant(owner, "supplier", suffix)
            rows.append(
                {
                    "id": base["id"],
                    "owner_id": base["owner_id"],
                    "name": base["name"],
                    "email": base["email"],
                    "phone": base["phone"],
                    "category": scenario["supplier_category"][suffix],
                    "contract_notes": scenario["supplier_contract_note"][suffix],
                    "status": "active",
                }
            )
    return rows


def generate_partners(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        scenario = owner_scenario(owner)
        for suffix in ROLE_SUFFIXES:
            base = _participant(owner, "partner", suffix)
            rows.append(
                {
                    "id": base["id"],
                    "owner_id": base["owner_id"],
                    "name": base["name"],
                    "email": base["email"],
                    "phone": base["phone"],
                    "partner_type": scenario["partner_types"][suffix],
                    "notes": scenario["partner_note"],
                    "status": "active",
                }
            )
    return rows


def generate_investors(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        scenario = owner_scenario(owner)
        for suffix in ROLE_SUFFIXES:
            base = _participant(owner, "investor", suffix)
            rows.append(
                {
                    "id": base["id"],
                    "owner_id": base["owner_id"],
                    "name": base["name"],
                    "email": base["email"],
                    "phone": base["phone"],
                    "focus": scenario["investor_focus"][suffix],
                    "notes": scenario["investor_note"],
                    "status": "active",
                }
            )
    return rows


def generate_orders(
    customers: list[dict[str, Any]], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    products_by_owner = _group_by_owner(products)
    for customer in customers:
        owner_products = products_by_owner[customer["owner_id"]]
        primary = owner_products[0]
        secondary = owner_products[1]
        rows.append(
            {
                "id": seed_uuid("order", customer["id"], "recent"),
                "owner_id": customer["owner_id"],
                "customer_id": customer["id"],
                "product_id": primary["id"],
                "quantity": 2,
                "total_price": str(
                    (Decimal(primary["selling_price"]) * 2).quantize(Decimal("0.01"))
                ),
                "order_date": (REFERENCE_DATE - timedelta(days=3)).isoformat(),
                "status": "paid",
                "channel": "website",
            }
        )
        rows.append(
            {
                "id": seed_uuid("order", customer["id"], "older"),
                "owner_id": customer["owner_id"],
                "customer_id": customer["id"],
                "product_id": secondary["id"],
                "quantity": 1,
                "total_price": str(Decimal(secondary["selling_price"]).quantize(Decimal("0.01"))),
                "order_date": (REFERENCE_DATE - timedelta(days=30)).isoformat(),
                "status": "paid",
                "channel": "telegram",
            }
        )
    return rows


def generate_supply_contracts(
    suppliers: list[dict[str, Any]], products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    products_by_owner = _group_by_owner(products)
    for supplier in suppliers:
        for product in products_by_owner[supplier["owner_id"]][:2]:
            rows.append(
                {
                    "id": seed_uuid("supplier-product", supplier["id"], product["id"]),
                    "owner_id": supplier["owner_id"],
                    "supplier_id": supplier["id"],
                    "product_id": product["id"],
                    "supply_price": product["cost_price"],
                    "stock_we_buy": 120,
                    "contract": f"Supply agreement for {product['name']}",
                    "lead_time_days": 10,
                    "contract_start": (REFERENCE_DATE - timedelta(days=45)).isoformat(),
                    "contract_end": (REFERENCE_DATE + timedelta(days=365)).isoformat(),
                    "is_active": "true",
                    "notes": f"Deterministic demo supplier contract for owner {supplier['owner_id']}",
                }
            )
    return rows


def generate_partner_agreements(partners: list[dict[str, Any]]) -> list[dict[str, Any]]:
    share = {"A": "10.00", "B": "8.50", "C": "12.00"}
    rows: list[dict[str, Any]] = []
    for partner in partners:
        suffix = partner["email"].split("@")[0][-1].upper()
        rows.append(
            {
                "id": seed_uuid("partner-agreement", partner["id"]),
                "owner_id": partner["owner_id"],
                "partner_id": partner["id"],
                "description": f"Partnership agreement for {partner['name']}",
                "agreement_type": partner["partner_type"],
                "revenue_share_pct": share[suffix],
                "start_date": (REFERENCE_DATE - timedelta(days=60)).isoformat(),
                "end_date": (REFERENCE_DATE + timedelta(days=365)).isoformat(),
                "is_active": "true",
                "notes": f"Demo agreement {suffix} with measurable KPIs",
            }
        )
    return rows


def generate_partner_products(
    partners: list[dict[str, Any]], products: list[dict[str, Any]], agreements: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    agreement_by_partner = {a["partner_id"]: a for a in agreements}
    products_by_owner = _group_by_owner(products)
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
                    "external_id": entry["phone"],
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


def generate_conversation_threads(
    customers: list[dict[str, Any]],
    suppliers: list[dict[str, Any]],
    partners: list[dict[str, Any]],
    investors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    title_prefix = {
        "customer": "Order and delivery",
        "supplier": "Supply and lead time",
        "partner": "Campaign and conversion",
        "investor": "Performance and outlook",
    }
    for role, entries in (
        ("customer", customers),
        ("supplier", suppliers),
        ("partner", partners),
        ("investor", investors),
    ):
        for entry in entries:
            if _email_suffix(entry["email"]) == "C":
                continue
            rows.append(
                {
                    "id": seed_uuid("conversation-thread", role, entry["id"]),
                    "owner_id": entry["owner_id"],
                    "thread_type": "external_sender",
                    "title": f"{title_prefix[role]} - {entry['name']}",
                    "sender_external_id": entry["email"].lower(),
                    "sender_name": entry["name"],
                    "sender_role": role,
                    "sender_channel": "email",
                }
            )
    return rows


def generate_messages(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for thread in threads:
        scenario = OWNER_SCENARIOS[_owner_label_from_seed_email(thread["sender_external_id"])]
        rows.append(
            {
                "id": seed_uuid("message", thread["id"], "inbound", "1"),
                "owner_id": thread["owner_id"],
                "conversation_thread_id": thread["id"],
                "sender_id": thread["sender_external_id"],
                "sender_name": thread["sender_name"],
                "sender_role": thread["sender_role"],
                "direction": "inbound",
                "content": scenario["message_inbound"][thread["sender_role"]],
            }
        )
        rows.append(
            {
                "id": seed_uuid("message", thread["id"], "outbound", "1"),
                "owner_id": thread["owner_id"],
                "conversation_thread_id": thread["id"],
                "sender_id": thread["sender_external_id"],
                "sender_name": thread["sender_name"],
                "sender_role": thread["sender_role"],
                "direction": "outbound",
                "content": scenario["message_outbound"][thread["sender_role"]],
            }
        )
    return rows


def generate_owner_memory_rules(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        if owner["label"] == "owner1":
            customer_rule = "Do not offer workspace bundle discounts above 12 percent or promise same-week dispatch unless stock is confirmed."
            supplier_rule = "For component shortages, prioritize supply reliability and onboarding kits over lowest landed cost."
        else:
            customer_rule = "Do not approve wholesale café pricing changes above 10 percent or custom packaging exceptions without owner approval."
            supplier_rule = "Protect delivery consistency for packaging and launch items even if a lower-cost supplier is available."
        rows.extend(
            [
                {
                    "id": seed_uuid("owner-memory-rule", owner["id"], "customer", "pricing"),
                    "owner_id": owner["id"],
                    "role": "customer",
                    "category": "pricing",
                    "content": customer_rule,
                    "created_at": "2026-03-20T09:00:00+00:00",
                    "updated_at": "2026-03-27T09:30:00+00:00",
                },
                {
                    "id": seed_uuid("owner-memory-rule", owner["id"], "supplier", "operations"),
                    "owner_id": owner["id"],
                    "role": "supplier",
                    "category": "operations",
                    "content": supplier_rule,
                    "created_at": "2026-03-18T08:30:00+00:00",
                    "updated_at": "2026-03-25T10:15:00+00:00",
                },
            ]
        )
    return rows


def generate_memory_entries(
    customers: list[dict[str, Any]],
    suppliers: list[dict[str, Any]],
    partners: list[dict[str, Any]],
    investors: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_owner_customers = _group_by_owner(customers)
    by_owner_suppliers = _group_by_owner(suppliers)
    by_owner_partners = _group_by_owner(partners)
    by_owner_investors = _group_by_owner(investors)

    for owner_id, owner_customers in by_owner_customers.items():
        customer_a = next(c for c in owner_customers if _email_suffix(c["email"]) == "A")
        supplier_a = next(
            s for s in by_owner_suppliers[owner_id] if _email_suffix(s["email"]) == "A"
        )
        partner_b = next(p for p in by_owner_partners[owner_id] if _email_suffix(p["email"]) == "B")
        investor_c = next(
            i for i in by_owner_investors[owner_id] if _email_suffix(i["email"]) == "C"
        )
        owner_label = _owner_label_from_seed_email(customer_a["email"])

        if owner_label == "owner1":
            rows.extend(
                [
                    {
                        "id": seed_uuid("memory-entry", owner_id, "customer-a", "ops"),
                        "owner_id": owner_id,
                        "sender_id": customer_a["email"],
                        "sender_name": customer_a["name"],
                        "sender_role": "customer",
                        "memory_type": "operations",
                        "content": "Customer wants bundle quote, stock confirmation, and delivery ETA combined in a single approval-ready reply.",
                        "summary": "Customer prefers one-message quote + ETA",
                        "tags": json.dumps(
                            ["customer-preference", "sales-flow", "workspace-bundles"]
                        ),
                        "importance": "0.78",
                        "created_at": "2026-03-22T09:40:00+00:00",
                    },
                    {
                        "id": seed_uuid("memory-entry", owner_id, "supplier-a", "risk"),
                        "owner_id": owner_id,
                        "sender_id": supplier_a["email"],
                        "sender_name": supplier_a["name"],
                        "sender_role": "supplier",
                        "memory_type": "risk",
                        "content": "Supplier flagged keyboard switch volatility; protect onboarding-kit stock with a 3-week buffer.",
                        "summary": "Protect onboarding-kit stock buffer",
                        "tags": json.dumps(["supply-risk", "inventory", "bundles"]),
                        "importance": "0.84",
                        "created_at": "2026-03-24T11:15:00+00:00",
                    },
                    {
                        "id": seed_uuid("memory-entry", owner_id, "partner-b", "growth"),
                        "owner_id": owner_id,
                        "sender_id": partner_b["email"],
                        "sender_name": partner_b["name"],
                        "sender_role": "partner",
                        "memory_type": "growth",
                        "content": "Partner performs better when weekly bundle availability and fitout-ready offers are sent every Monday morning.",
                        "summary": "Weekly bundle update drives partner leads",
                        "tags": json.dumps(["partner", "cadence", "lead-gen"]),
                        "importance": "0.66",
                        "created_at": "2026-03-26T07:55:00+00:00",
                    },
                    {
                        "id": seed_uuid("memory-entry", owner_id, "investor-c", "finance"),
                        "owner_id": owner_id,
                        "sender_id": investor_c["email"],
                        "sender_name": investor_c["name"],
                        "sender_role": "investor",
                        "memory_type": "finance",
                        "content": "Investor wants bundle margin trend tied to repeat-order rate and stock risk in the monthly review.",
                        "summary": "Investor tracks bundle margin + repeat orders",
                        "tags": json.dumps(["finance", "investor-reporting", "repeat-orders"]),
                        "importance": "0.81",
                        "created_at": "2026-03-28T14:20:00+00:00",
                    },
                ]
            )
        else:
            rows.extend(
                [
                    {
                        "id": seed_uuid("memory-entry", owner_id, "customer-a", "ops"),
                        "owner_id": owner_id,
                        "sender_id": customer_a["email"],
                        "sender_name": customer_a["name"],
                        "sender_role": "customer",
                        "memory_type": "operations",
                        "content": "Customer wants MOQ, delivery day, and branding options combined into a single reorder-ready message.",
                        "summary": "Customer prefers reorder-ready MOQ + delivery summary",
                        "tags": json.dumps(["customer-preference", "wholesale", "reorder"]),
                        "importance": "0.78",
                        "created_at": "2026-03-22T09:40:00+00:00",
                    },
                    {
                        "id": seed_uuid("memory-entry", owner_id, "supplier-a", "risk"),
                        "owner_id": owner_id,
                        "sender_id": supplier_a["email"],
                        "sender_name": supplier_a["name"],
                        "sender_role": "supplier",
                        "memory_type": "risk",
                        "content": "Packaging supplier warned that printed cup lead times stretch during promo periods; lock artwork earlier.",
                        "summary": "Printed cup lead time risk before promos",
                        "tags": json.dumps(["supply-risk", "packaging", "promo-planning"]),
                        "importance": "0.84",
                        "created_at": "2026-03-24T11:15:00+00:00",
                    },
                    {
                        "id": seed_uuid("memory-entry", owner_id, "partner-b", "growth"),
                        "owner_id": owner_id,
                        "sender_id": partner_b["email"],
                        "sender_name": partner_b["name"],
                        "sender_role": "partner",
                        "memory_type": "growth",
                        "content": "Partner converts best when launch packs include ready-to-post seasonal copy and stock-safe pricing.",
                        "summary": "Seasonal launch packs improve partner conversion",
                        "tags": json.dumps(["partner", "campaign", "seasonal-offer"]),
                        "importance": "0.66",
                        "created_at": "2026-03-26T07:55:00+00:00",
                    },
                    {
                        "id": seed_uuid("memory-entry", owner_id, "investor-c", "finance"),
                        "owner_id": owner_id,
                        "sender_id": investor_c["email"],
                        "sender_name": investor_c["name"],
                        "sender_role": "investor",
                        "memory_type": "finance",
                        "content": "Investor wants wholesale reorder trend, packaging margin, and campaign ROI reviewed together every month.",
                        "summary": "Investor tracks reorder trend + campaign ROI",
                        "tags": json.dumps(["finance", "investor-reporting", "wholesale-growth"]),
                        "importance": "0.81",
                        "created_at": "2026-03-28T14:20:00+00:00",
                    },
                ]
            )
    return rows


def generate_entity_memories(
    customers: list[dict[str, Any]], suppliers: list[dict[str, Any]], partners: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, entries, content in (
        ("customer", customers, "Prefers concise ETA + terms, responds fastest before lunch."),
        ("supplier", suppliers, "Reliable on quality, slower confirmation during month-end."),
        ("partner", partners, "Performs best when provided weekly product availability snapshot."),
    ):
        for entry in entries:
            if _email_suffix(entry["email"]) != "A":
                continue
            rows.append(
                {
                    "id": seed_uuid("entity-memory", role, entry["id"]),
                    "owner_id": entry["owner_id"],
                    "entity_role": role,
                    "entity_id": entry["id"],
                    "memory_type": "working-style",
                    "content": content,
                    "summary": f"{entry['name']} working style baseline",
                    "tags": json.dumps([role, "working-style"]),
                    "importance": 2,
                    "created_at": "2026-03-19T10:00:00+00:00",
                    "updated_at": "2026-03-29T10:00:00+00:00",
                }
            )
    return rows


def generate_conversation_memories(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for thread in threads:
        rows.append(
            {
                "id": seed_uuid("conversation-memory", thread["id"]),
                "owner_id": thread["owner_id"],
                "conversation_thread_id": thread["id"],
                "entity_role": thread["sender_role"],
                "entity_id": None,
                "summary": f"Historical recap: {thread['sender_name']} aligned on timelines and requested structured updates.",
                "keywords": json.dumps(["timeline", "follow-up", "weekly-status"]),
                "happened_at": "2026-03-30T12:00:00+00:00",
                "created_at": "2026-03-30T12:10:00+00:00",
            }
        )
    return rows


def generate_conversation_sender_memories(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for thread in threads:
        rows.append(
            {
                "id": seed_uuid("conversation-sender-memory", thread["id"]),
                "owner_id": thread["owner_id"],
                "conversation_thread_id": thread["id"],
                "sender_external_id": thread["sender_external_id"],
                "sender_name": thread["sender_name"],
                "sender_role": thread["sender_role"],
                "summary": f"Daily work note: prepared recap for {thread['sender_name']} and queued next action checklist.",
                "message_count_since_update": 2,
                "last_message_at": "2026-03-31T08:45:00+00:00",
                "last_summarized_at": "2026-03-31T09:00:00+00:00",
                "created_at": "2026-03-31T09:00:00+00:00",
                "updated_at": "2026-03-31T09:00:00+00:00",
            }
        )
    return rows


def generate_daily_digests(owners: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for owner in owners:
        if owner["label"] == "owner1":
            title_1 = "Northstar Daily Ops - Bundle availability and supplier cover"
            summary_1 = "Reviewed onboarding bundle stock, confirmed one supplier buffer action, and kept all quotes margin-safe."
            title_2 = "Northstar Daily Ops - Customer follow-ups and repeat orders"
            summary_2 = "Closed two customer quote threads, captured one buying preference, and queued investor notes on repeat-order momentum."
        else:
            title_1 = "Luna Daily Ops - Packaging lead times and promo planning"
            summary_1 = "Reviewed print lead times, aligned next wholesale promo timing, and protected packaging margin before launch."
            title_2 = "Luna Daily Ops - Reorders and café growth signals"
            summary_2 = "Closed reorder conversations, captured one branding preference, and prepared investor notes on wholesale repeat demand."
        rows.extend(
            [
                {
                    "id": seed_uuid("daily-digest", owner["id"], "day-1"),
                    "owner_id": owner["id"],
                    "title": title_1,
                    "summary": summary_1,
                    "risk": "medium",
                    "created_at": "2026-03-30T18:00:00+00:00",
                },
                {
                    "id": seed_uuid("daily-digest", owner["id"], "day-2"),
                    "owner_id": owner["id"],
                    "title": title_2,
                    "summary": summary_2,
                    "risk": "low",
                    "created_at": "2026-03-31T18:00:00+00:00",
                },
            ]
        )
    return rows


def generate_memory_update_proposals(customers: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_owner = _group_by_owner(customers)
    rows: list[dict[str, Any]] = []
    for owner_id, owner_customers in by_owner.items():
        pending = next(c for c in owner_customers if _email_suffix(c["email"]) == "A")
        approved = next(c for c in owner_customers if _email_suffix(c["email"]) == "B")
        owner_label = _owner_label_from_seed_email(pending["email"])
        pending_content = (
            "Prefers stock-safe bundle quote, delivery ETA, and final terms in one approval-ready message."
            if owner_label == "owner1"
            else "Prefers MOQ, delivery day, and branding options grouped into one reorder-ready reply."
        )
        pending_summary = (
            "Bundle quote + ETA preference"
            if owner_label == "owner1"
            else "MOQ + delivery + branding preference"
        )
        approved_content = (
            "Accepted staged billing for larger team-setup orders with standard safeguards."
            if owner_label == "owner1"
            else "Accepted standard wholesale payment terms for recurring café packaging orders."
        )
        approved_summary = (
            "Staged billing accepted for team orders"
            if owner_label == "owner1"
            else "Wholesale payment terms accepted"
        )
        rows.append(
            {
                "id": seed_uuid("memory-proposal", owner_id, "pending", pending["id"]),
                "owner_id": owner_id,
                "target_table": "customers",
                "target_id": pending["id"],
                "proposed_content": json.dumps(
                    [
                        {
                            "sender_id": pending["email"],
                            "sender_name": pending["name"],
                            "sender_role": "customer",
                            "memory_type": "preference",
                            "content": pending_content,
                            "summary": pending_summary,
                            "tags": ["communication", "preference"],
                            "importance": 0.72,
                        }
                    ],
                    separators=(",", ":"),
                ),
                "reason": "Detected stable sales-communication preference from repeated demo interactions.",
                "risk_level": "medium",
                "status": "pending",
            }
        )
        rows.append(
            {
                "id": seed_uuid("memory-proposal", owner_id, "approved", approved["id"]),
                "owner_id": owner_id,
                "target_table": "customers",
                "target_id": approved["id"],
                "proposed_content": json.dumps(
                    [
                        {
                            "sender_id": approved["email"],
                            "sender_name": approved["name"],
                            "sender_role": "customer",
                            "memory_type": "billing",
                            "content": approved_content,
                            "summary": approved_summary,
                            "tags": ["finance"],
                            "importance": 0.63,
                        }
                    ],
                    separators=(",", ":"),
                ),
                "reason": "Owner previously approved this commercial memory update.",
                "risk_level": "low",
                "status": "approved",
            }
        )
    return rows


def generate_held_replies(threads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return []


def generate_reply_review_records(held_replies: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return []


def generate_pending_approvals(memory_proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for proposal in memory_proposals:
        if proposal["status"] != "pending":
            continue
        rows.append(
            {
                "id": seed_uuid("pending-approval", "memory", proposal["id"]),
                "owner_id": proposal["owner_id"],
                "title": "Memory update requires review",
                "sender": "Memory Agent",
                "preview": "Detected a stable contact preference update.",
                "proposal_type": "memory-update",
                "risk_level": proposal["risk_level"],
                "status": "pending",
                "proposal_id": proposal["id"],
                "held_reply_id": "",
            }
        )
    return rows


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
    conversation_threads = generate_conversation_threads(customers, suppliers, partners, investors)
    messages = generate_messages(conversation_threads)
    owner_memory_rules = generate_owner_memory_rules(owners)
    memory_entries = generate_memory_entries(customers, suppliers, partners, investors)
    entity_memories = generate_entity_memories(customers, suppliers, partners)
    conversation_memories = generate_conversation_memories(conversation_threads)
    conversation_sender_memories = generate_conversation_sender_memories(conversation_threads)
    daily_digests = generate_daily_digests(owners)
    memory_update_proposals = generate_memory_update_proposals(customers)
    held_replies = generate_held_replies(conversation_threads)
    reply_review_records = generate_reply_review_records(held_replies)
    pending_approvals = generate_pending_approvals(memory_update_proposals)

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
        "owner_memory_rules.csv",
        owner_memory_rules,
        ["id", "owner_id", "role", "category", "content", "created_at", "updated_at"],
    )
    write_csv(
        "memory_entries.csv",
        memory_entries,
        [
            "id",
            "owner_id",
            "sender_id",
            "sender_name",
            "sender_role",
            "memory_type",
            "content",
            "summary",
            "tags",
            "importance",
            "created_at",
        ],
    )
    write_csv(
        "entity_memories.csv",
        entity_memories,
        [
            "id",
            "owner_id",
            "entity_role",
            "entity_id",
            "memory_type",
            "content",
            "summary",
            "tags",
            "importance",
            "created_at",
            "updated_at",
        ],
    )
    write_csv(
        "conversation_memories.csv",
        conversation_memories,
        [
            "id",
            "owner_id",
            "conversation_thread_id",
            "entity_role",
            "entity_id",
            "summary",
            "keywords",
            "happened_at",
            "created_at",
        ],
    )
    write_csv(
        "conversation_sender_memories.csv",
        conversation_sender_memories,
        [
            "id",
            "owner_id",
            "conversation_thread_id",
            "sender_external_id",
            "sender_name",
            "sender_role",
            "summary",
            "message_count_since_update",
            "last_message_at",
            "last_summarized_at",
            "created_at",
            "updated_at",
        ],
    )
    write_csv(
        "daily_digest.csv",
        daily_digests,
        ["id", "owner_id", "title", "summary", "risk", "created_at"],
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
