from backend.db.engine import engine, SessionLocal
from backend.db.orm_models import (
    Product, Customer, Order, Supplier,
    SupplyContract, Partner, PartnerAgreement, PartnerProduct,
)
from sqlalchemy import inspect, func


def verify_schema():
    """Check that all expected tables exist with their columns."""
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Found {len(tables)} tables:")
    for table in sorted(tables):
        columns = [col["name"] for col in inspector.get_columns(table)]
        print(f"  {table}: {', '.join(columns)}")
    return tables


def verify_row_counts():
    """Check that each table has the expected number of rows."""
    expected = {
        Product: 30,
        Customer: 20,
        Order: 120,
        Supplier: 5,
        SupplyContract: 30,
        Partner: 3,
        PartnerAgreement: 3,
        PartnerProduct: 15,
    }

    session = SessionLocal()
    all_pass = True
    try:
        print("\nRow counts:")
        for model, expected_count in expected.items():
            actual = session.query(func.count(model.id)).scalar()
            status = "OK" if actual == expected_count else "MISMATCH"
            if status == "MISMATCH":
                all_pass = False
            print(f"  {model.__tablename__}: {actual} rows (expected {expected_count}) [{status}]")
    finally:
        session.close()
    return all_pass


def verify_foreign_keys():
    """Check that foreign key references are valid (no orphaned rows)."""
    session = SessionLocal()
    errors = []
    try:
        print("\nForeign key checks:")

        # Orders → customers
        orphaned = session.query(Order).filter(
            ~Order.customer_id.in_(session.query(Customer.id))
        ).count()
        if orphaned:
            errors.append(f"  orders: {orphaned} rows with invalid customer_id")

        # Orders → products
        orphaned = session.query(Order).filter(
            ~Order.product_id.in_(session.query(Product.id))
        ).count()
        if orphaned:
            errors.append(f"  orders: {orphaned} rows with invalid product_id")

        # SupplyContracts → suppliers
        orphaned = session.query(SupplyContract).filter(
            ~SupplyContract.supplier_id.in_(session.query(Supplier.id))
        ).count()
        if orphaned:
            errors.append(f"  supply_contracts: {orphaned} rows with invalid supplier_id")

        # SupplyContracts → products
        orphaned = session.query(SupplyContract).filter(
            ~SupplyContract.product_id.in_(session.query(Product.id))
        ).count()
        if orphaned:
            errors.append(f"  supply_contracts: {orphaned} rows with invalid product_id")

        # PartnerAgreements → partners
        orphaned = session.query(PartnerAgreement).filter(
            ~PartnerAgreement.partner_id.in_(session.query(Partner.id))
        ).count()
        if orphaned:
            errors.append(f"  partner_agreements: {orphaned} rows with invalid partner_id")

        # PartnerProducts → partners, products, agreements
        for fk_col, ref_model in [
            (PartnerProduct.partner_id, Partner),
            (PartnerProduct.product_id, Product),
            (PartnerProduct.agreement_id, PartnerAgreement),
        ]:
            orphaned = session.query(PartnerProduct).filter(
                ~fk_col.in_(session.query(ref_model.id))
            ).count()
            if orphaned:
                errors.append(f"  partner_products: {orphaned} rows with invalid {fk_col.key}")

        if errors:
            for e in errors:
                print(e)
        else:
            print("  All foreign keys valid.")
    finally:
        session.close()
    return len(errors) == 0


def verify_sample_data():
    """Spot-check a few known seed values."""
    session = SessionLocal()
    try:
        print("\nSample data checks:")

        p = session.query(Product).filter_by(name="Wireless Bluetooth Earbuds").first()
        assert p is not None, "Product 'Wireless Bluetooth Earbuds' not found"
        assert p.category == "Electronics"
        print(f"  Product: {p.name} (${p.selling_price}, {p.category}) OK")

        s = session.query(Supplier).filter_by(name="Shenzhen TechParts Co.").first()
        assert s is not None, "Supplier 'Shenzhen TechParts Co.' not found"
        print(f"  Supplier: {s.name} ({s.contact_person}) OK")

        c = session.query(Customer).filter_by(name="James Tan").first()
        assert c is not None, "Customer 'James Tan' not found"
        print(f"  Customer: {c.name} ({c.platform}) OK")

        print("  Sample data verified.")
    finally:
        session.close()


if __name__ == "__main__":
    tables = verify_schema()
    counts_ok = verify_row_counts()
    fk_ok = verify_foreign_keys()
    verify_sample_data()

    print("\n" + "=" * 40)
    if counts_ok and fk_ok:
        print("ALL CHECKS PASSED")
    else:
        print("SOME CHECKS FAILED")
