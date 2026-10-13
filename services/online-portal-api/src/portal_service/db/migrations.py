"""Database migrations, schema creation, and realistic initial seed data."""

import json
import logging
from sqlalchemy.orm import Session

from portal_service.db.session import engine, Base
from portal_service.db.models import (
    PortalStaffUser,
    StaffRole,
    Customer,
    Category,
    Product,
    Order,
    OrderItem,
    OrderStatusHistory,
    PortalAuditLog,
    StockStatusEnum,
    FulfillmentTypeEnum,
    PaymentMethodEnum,
    OrderStatusEnum,
)
from portal_service.security.password import hash_password

logger = logging.getLogger("portal_service.db.migrations")


def init_db():
    """Create all tables for the online portal database."""
    logger.info("Initializing Online Pharmacy Portal database schema...")
    Base.metadata.create_all(bind=engine)
    logger.info("Online Portal database schema initialized.")


def seed_default_data(db: Session) -> None:
    """Seed initial staff users, categories, products, customer, and sample orders."""
    # 1. Staff Users
    staff_count = db.query(PortalStaffUser).count()
    if staff_count == 0:
        logger.info("Seeding default staff users...")
        staff_members = [
            PortalStaffUser(
                email="admin@apexhealthcare.com",
                password_hash=hash_password("AdminPassword2026!"),
                full_name="Dr. Sunita Rao (Chief Administrator)",
                role=StaffRole.ADMIN.value,
                is_active=True,
            ),
            PortalStaffUser(
                email="pharmacist@apexhealthcare.com",
                password_hash=hash_password("PharmSecure2026!"),
                full_name="Rajesh Varma, Reg. Pharmacist #AP-8841",
                role=StaffRole.PHARMACIST.value,
                is_active=True,
            ),
            PortalStaffUser(
                email="staff@apexhealthcare.com",
                password_hash=hash_password("StaffPass2026!"),
                full_name="Priya Sharma (Fulfillment Staff)",
                role=StaffRole.STAFF.value,
                is_active=True,
            ),
        ]
        db.add_all(staff_members)
        db.commit()
        logger.info("Seeded 3 default staff accounts.")

    # 2. Categories
    category_count = db.query(Category).count()
    if category_count == 0:
        logger.info("Seeding product categories...")
        categories = [
            Category(
                name="Prescription Medicines",
                slug="prescription-medicines",
                description="Antibiotics, cardiovascular, anti-diabetic and schedule H/X pharmaceuticals requiring pharmacist prescription review.",
                display_order=1,
                is_active=True,
            ),
            Category(
                name="Pain Relief & Fever",
                slug="pain-relief-fever",
                description="Over-the-counter analgesics, antipyretics, headache and muscle ache relief remedies.",
                display_order=2,
                is_active=True,
            ),
            Category(
                name="Cough, Cold & Immunity",
                slug="cough-cold-immunity",
                description="Syrups, decongestants, throat lozenges, and immune defense supplements.",
                display_order=3,
                is_active=True,
            ),
            Category(
                name="Digestive Health & Antacids",
                slug="digestive-health",
                description="Antacids, proton pump inhibitors, probiotics, oral rehydration, and liver tonics.",
                display_order=4,
                is_active=True,
            ),
            Category(
                name="Chronic Care & Diabetes",
                slug="chronic-care-diabetes",
                description="Glucose monitoring essentials, chronic metabolic therapy and vascular wellness.",
                display_order=5,
                is_active=True,
            ),
            Category(
                name="First Aid & Daily Wellness",
                slug="first-aid-wellness",
                description="Surgical dressings, antiseptics, vitamins, minerals, and daily hygiene essentials.",
                display_order=6,
                is_active=True,
            ),
        ]
        db.add_all(categories)
        db.commit()
        logger.info("Seeded 6 product categories.")

    # 3. Products
    product_count = db.query(Product).count()
    if product_count == 0:
        logger.info("Seeding initial pharmacy products...")
        cats = {c.slug: c.id for c in db.query(Category).all()}

        sample_products = [
            Product(
                category_id=cats["pain-relief-fever"],
                name="Paracetamol 650mg Tablets",
                slug="paracetamol-650mg-tablets",
                generic_name="Paracetamol (Acetaminophen)",
                dosage_form="Tablet",
                pack_size="Strip of 15 Tablets",
                mrp_paise=3500,  # ₹35.00
                selling_price_paise=3000,  # ₹30.00
                is_prescription_required=False,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&q=80",
                description="Fast-acting pain and fever reducer indicated for headaches, fever, and generalized mild-to-moderate pain.",
                usage_instructions="Adults: 1 tablet every 4 to 6 hours as needed. Do not exceed 4000mg in 24 hours.",
                side_effects="Generally well tolerated at prescribed dosages. Rare: allergic rash or hepatic distress with overdose.",
            ),
            Product(
                category_id=cats["prescription-medicines"],
                name="Amoxicillin 500mg Capsules",
                slug="amoxicillin-500mg-capsules",
                generic_name="Amoxicillin Trihydrate",
                dosage_form="Capsule",
                pack_size="Strip of 10 Capsules",
                mrp_paise=12500,  # ₹125.00
                selling_price_paise=11000,  # ₹110.00
                is_prescription_required=True,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1471864190281-a93a3070b6de?w=400&q=80",
                description="Broad-spectrum penicillin-class antibiotic for ear, throat, respiratory and urinary tract bacterial infections.",
                usage_instructions="Take 1 capsule every 8 hours with or after meals. Complete the entire prescribed course.",
                side_effects="Nausea, diarrhea, abdominal discomfort. Seek immediate attention if skin rash or swelling occurs.",
            ),
            Product(
                category_id=cats["prescription-medicines"],
                name="Azithromycin 500mg Tablets",
                slug="azithromycin-500mg-tablets",
                generic_name="Azithromycin",
                dosage_form="Tablet",
                pack_size="Strip of 3 Tablets",
                mrp_paise=13500,  # ₹135.00
                selling_price_paise=12000,  # ₹120.00
                is_prescription_required=True,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1550572017-edd951aa8f72?w=400&q=80",
                description="Macrolide antibiotic commonly prescribed for upper respiratory tract and skin infections.",
                usage_instructions="Take 1 tablet once daily, preferably 1 hour before or 2 hours after a meal for 3 consecutive days.",
                side_effects="Loose stools, stomach cramps, temporary taste alteration.",
            ),
            Product(
                category_id=cats["chronic-care-diabetes"],
                name="Metformin Hydrochloride 500mg SR",
                slug="metformin-500mg-sr",
                generic_name="Metformin Hydrochloride (Sustained Release)",
                dosage_form="Tablet",
                pack_size="Strip of 20 Tablets",
                mrp_paise=5500,  # ₹55.00
                selling_price_paise=4800,  # ₹48.00
                is_prescription_required=True,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1587854692152-cbe660dbde88?w=400&q=80",
                description="First-line antidiabetic medication for the glycemic management of Type 2 Diabetes Mellitus.",
                usage_instructions="Take once or twice daily with evening meals as directed by your physician.",
                side_effects="Mild nausea, metallic taste, digestive upset during initial titration.",
            ),
            Product(
                category_id=cats["chronic-care-diabetes"],
                name="Atorvastatin 10mg Tablets",
                slug="atorvastatin-10mg-tablets",
                generic_name="Atorvastatin Calcium",
                dosage_form="Tablet",
                pack_size="Strip of 15 Tablets",
                mrp_paise=10500,  # ₹105.00
                selling_price_paise=9200,  # ₹92.00
                is_prescription_required=True,
                is_available=True,
                stock_status=StockStatusEnum.LOW_STOCK.value,
                image_url="https://images.unsplash.com/photo-1584017911766-d451b3d0e843?w=400&q=80",
                description="Statin lipid-lowering medication to reduce cardiovascular disease risk and elevated cholesterol.",
                usage_instructions="Take 1 tablet daily at bedtime, with or without food.",
                side_effects="Muscle ache, fatigue, mild headache.",
            ),
            Product(
                category_id=cats["cough-cold-immunity"],
                name="Cetirizine Hydrochloride 10mg",
                slug="cetirizine-10mg-tablets",
                generic_name="Cetirizine HCl",
                dosage_form="Tablet",
                pack_size="Strip of 10 Tablets",
                mrp_paise=2800,  # ₹28.00
                selling_price_paise=2400,  # ₹24.00
                is_prescription_required=False,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1628771065518-0d82f1938462?w=400&q=80",
                description="Second-generation antihistamine relieving allergic rhinitis, watery eyes, sneezing and hives.",
                usage_instructions="Adults and children over 12: 1 tablet once daily in the evening.",
                side_effects="Mild drowsiness in sensitive individuals, dry mouth.",
            ),
            Product(
                category_id=cats["digestive-health"],
                name="Omeprazole 20mg Delayed-Release",
                slug="omeprazole-20mg-capsules",
                generic_name="Omeprazole",
                dosage_form="Capsule",
                pack_size="Strip of 15 Capsules",
                mrp_paise=6200,  # ₹62.00
                selling_price_paise=5400,  # ₹54.00
                is_prescription_required=False,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1585435557343-3b092031a831?w=400&q=80",
                description="Proton pump inhibitor decreasing stomach acid secretion for acid reflux and heartburn.",
                usage_instructions="Swallow 1 capsule whole with water 30 minutes before breakfast.",
                side_effects="Headache, gas, mild nausea.",
            ),
            Product(
                category_id=cats["digestive-health"],
                name="Electrolyte Hydration ORS Sachet",
                slug="electrolyte-ors-sachet",
                generic_name="WHO Formula Oral Rehydration Salts",
                dosage_form="Powder",
                pack_size="Pack of 4 Sachets (21.8g each)",
                mrp_paise=2500,  # ₹25.00
                selling_price_paise=2200,  # ₹22.00
                is_prescription_required=False,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1576602976047-174e57a47881?w=400&q=80",
                description="Balanced electrolyte replacement solution restoring hydration during dehydration or heat exhaustion.",
                usage_instructions="Dissolve entire contents of 1 sachet in 1 liter of clean drinking water.",
                side_effects="None when properly diluted.",
            ),
            Product(
                category_id=cats["first-aid-wellness"],
                name="Vitamin C 500mg with Zinc Chewable",
                slug="vitamin-c-zinc-chewable",
                generic_name="Ascorbic Acid & Elemental Zinc",
                dosage_form="Chewable Tablet",
                pack_size="Bottle of 60 Chewables",
                mrp_paise=12000,  # ₹120.00
                selling_price_paise=9500,  # ₹95.00
                is_prescription_required=False,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1550572017-4fcdbb59cc32?w=400&q=80",
                description="Delicious citrus-flavored chewable nutritional antioxidant supporting skin health and immune function.",
                usage_instructions="Chew 1 tablet daily after food.",
                side_effects="Generally safe; excessive intake may cause mild stomach upset.",
            ),
            Product(
                category_id=cats["first-aid-wellness"],
                name="Antiseptic Povidone Iodine Ointment 5%",
                slug="povidone-iodine-ointment-5",
                generic_name="Povidone Iodine IP 5% w/w",
                dosage_form="Ointment",
                pack_size="Tube of 20g",
                mrp_paise=6500,  # ₹65.00
                selling_price_paise=5800,  # ₹58.00
                is_prescription_required=False,
                is_available=True,
                stock_status=StockStatusEnum.IN_STOCK.value,
                image_url="https://images.unsplash.com/photo-1584308666744-24d5c474f2ae?w=400&q=80",
                description="Topical microbicidal ointment for the prevention and treatment of skin infections in minor cuts, scrapes and burns.",
                usage_instructions="Clean affected area and apply a thin layer 1 to 2 times daily. Cover with dressing if needed.",
                side_effects="Mild local irritation, temporary skin staining.",
            ),
        ]
        db.add_all(sample_products)
        db.commit()
        logger.info("Seeded 10 catalog products.")

    # 4. Demo Customer
    demo_customer = db.query(Customer).filter(Customer.email == "customer@example.com").first()
    if not demo_customer:
        logger.info("Seeding demo customer account...")
        demo_customer = Customer(
            email="customer@example.com",
            password_hash=hash_password("CustomerPass2026!"),
            full_name="Ramesh Kumar",
            phone="+91 98490 12345",
            delivery_address="Flat 302, Green Meadows Apartments, Jubilee Hills Road No. 10, Hyderabad 500033",
            is_active=True,
        )
        db.add(demo_customer)
        db.commit()
        logger.info("Seeded demo customer: customer@example.com")

    # 5. Demo Orders (if empty)
    order_count = db.query(Order).count()
    if order_count == 0 and demo_customer:
        logger.info("Seeding initial demonstration orders...")
        products_by_slug = {p.slug: p for p in db.query(Product).all()}

        # Order 1: OTC pickup order pending staff confirmation
        p_para = products_by_slug.get("paracetamol-650mg-tablets")
        p_cet = products_by_slug.get("cetirizine-10mg-tablets")
        if p_para and p_cet:
            order1 = Order(
                order_number="ORD-2026-1001",
                customer_id=demo_customer.id,
                customer_name=demo_customer.full_name,
                customer_email=demo_customer.email,
                customer_phone=demo_customer.phone,
                fulfillment_type=FulfillmentTypeEnum.PICKUP.value,
                delivery_address="In-Store Pickup",
                payment_method=PaymentMethodEnum.PAY_AT_PICKUP.value,
                status=OrderStatusEnum.PENDING_CONFIRMATION.value,
                subtotal_paise=p_para.selling_price_paise * 2 + p_cet.selling_price_paise * 1,
                delivery_fee_paise=0,
                total_paise=p_para.selling_price_paise * 2 + p_cet.selling_price_paise * 1,
                has_prescription_items=False,
                pharmacist_notes="",
                rejection_reason="",
            )
            db.add(order1)
            db.flush()

            item1_1 = OrderItem(
                order_id=order1.id,
                product_id=p_para.id,
                product_name=p_para.name,
                generic_name=p_para.generic_name,
                dosage_form=p_para.dosage_form,
                pack_size=p_para.pack_size,
                unit_price_paise=p_para.selling_price_paise,
                quantity=2,
                total_paise=p_para.selling_price_paise * 2,
                is_prescription_required=False,
            )
            item1_2 = OrderItem(
                order_id=order1.id,
                product_id=p_cet.id,
                product_name=p_cet.name,
                generic_name=p_cet.generic_name,
                dosage_form=p_cet.dosage_form,
                pack_size=p_cet.pack_size,
                unit_price_paise=p_cet.selling_price_paise,
                quantity=1,
                total_paise=p_cet.selling_price_paise * 1,
                is_prescription_required=False,
            )
            hist1 = OrderStatusHistory(
                order_id=order1.id,
                from_status=None,
                to_status=OrderStatusEnum.PENDING_CONFIRMATION.value,
                changed_by_type="CUSTOMER",
                changed_by_name=demo_customer.full_name,
                notes="Online order placed. Awaiting store confirmation.",
            )
            db.add_all([item1_1, item1_2, hist1])

        # Order 2: Prescription item delivery order requiring pharmacist review
        p_amox = products_by_slug.get("amoxicillin-500mg-capsules")
        p_ors = products_by_slug.get("electrolyte-ors-sachet")
        if p_amox and p_ors:
            order2 = Order(
                order_number="ORD-2026-1002",
                customer_id=demo_customer.id,
                customer_name=demo_customer.full_name,
                customer_email=demo_customer.email,
                customer_phone=demo_customer.phone,
                fulfillment_type=FulfillmentTypeEnum.DELIVERY.value,
                delivery_address=demo_customer.delivery_address,
                payment_method=PaymentMethodEnum.CASH_ON_DELIVERY.value,
                status=OrderStatusEnum.PHARMACIST_REVIEW.value,
                subtotal_paise=p_amox.selling_price_paise * 1 + p_ors.selling_price_paise * 2,
                delivery_fee_paise=4000,
                total_paise=p_amox.selling_price_paise * 1 + p_ors.selling_price_paise * 2 + 4000,
                has_prescription_items=True,
                pharmacist_notes="Prescription verification required before dispensing Amoxicillin 500mg.",
                rejection_reason="",
            )
            db.add(order2)
            db.flush()

            item2_1 = OrderItem(
                order_id=order2.id,
                product_id=p_amox.id,
                product_name=p_amox.name,
                generic_name=p_amox.generic_name,
                dosage_form=p_amox.dosage_form,
                pack_size=p_amox.pack_size,
                unit_price_paise=p_amox.selling_price_paise,
                quantity=1,
                total_paise=p_amox.selling_price_paise * 1,
                is_prescription_required=True,
            )
            item2_2 = OrderItem(
                order_id=order2.id,
                product_id=p_ors.id,
                product_name=p_ors.name,
                generic_name=p_ors.generic_name,
                dosage_form=p_ors.dosage_form,
                pack_size=p_ors.pack_size,
                unit_price_paise=p_ors.selling_price_paise,
                quantity=2,
                total_paise=p_ors.selling_price_paise * 2,
                is_prescription_required=False,
            )
            hist2_1 = OrderStatusHistory(
                order_id=order2.id,
                from_status=None,
                to_status=OrderStatusEnum.PENDING_CONFIRMATION.value,
                changed_by_type="CUSTOMER",
                changed_by_name=demo_customer.full_name,
                notes="Online order placed.",
            )
            hist2_2 = OrderStatusHistory(
                order_id=order2.id,
                from_status=OrderStatusEnum.PENDING_CONFIRMATION.value,
                to_status=OrderStatusEnum.PHARMACIST_REVIEW.value,
                changed_by_type="SYSTEM",
                changed_by_name="Pharmacy Workflow System",
                notes="Flagged for pharmacist review due to prescription-only items.",
            )
            db.add_all([item2_1, item2_2, hist2_1, hist2_2])

        db.commit()
        logger.info("Seeded 2 demonstration orders.")
