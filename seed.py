"""
Seed script — populates the database with:
  - Lens inventory SKUs
  - Coating inventory
  - 10 sample orders across various stages
Run: python scripts/seed.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from datetime import datetime, timedelta, timezone

from database import AsyncSessionLocal, init_db
from models.inventory import CoatingInventory, LensInventory
from models.order import (
    Coating, InvStatus, LensIndex, LensType, Order, OrderStage, OrderStatusLog,
)


def dt(days_ago: int) -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=days_ago)


LENS_SKUS = [
    dict(sku="SV-150-CLR", lens_type="Single Vision", lens_index="1.50", qty_in_stock=45, min_stock=20, sph_min=-6.0, sph_max=4.0, supplier_name="Essilor India", supplier_eta_days=2),
    dict(sku="SV-156-CLR", lens_type="Single Vision", lens_index="1.56", qty_in_stock=38, min_stock=20, sph_min=-6.0, sph_max=4.0, supplier_name="Essilor India", supplier_eta_days=2),
    dict(sku="SV-160-CLR", lens_type="Single Vision", lens_index="1.60", qty_in_stock=12, min_stock=20, sph_min=-8.0, sph_max=4.0, supplier_name="Zeiss India",   supplier_eta_days=3),
    dict(sku="SV-167-CLR", lens_type="Single Vision", lens_index="1.67", qty_in_stock=6,  min_stock=15, sph_min=-10.0,sph_max=4.0, supplier_name="Zeiss India",   supplier_eta_days=3),
    dict(sku="SV-174-CLR", lens_type="Single Vision", lens_index="1.74", qty_in_stock=3,  min_stock=10, sph_min=-12.0,sph_max=4.0, supplier_name="Hoya India",    supplier_eta_days=4),
    dict(sku="PROG-160",   lens_type="Progressive",   lens_index="1.60", qty_in_stock=14, min_stock=10, supplier_name="Zeiss India",   supplier_eta_days=4),
    dict(sku="PROG-167",   lens_type="Progressive",   lens_index="1.67", qty_in_stock=8,  min_stock=10, supplier_name="Hoya India",    supplier_eta_days=5),
    dict(sku="BIF-150",    lens_type="Bifocal",       lens_index="1.50", qty_in_stock=22, min_stock=15, supplier_name="Essilor India", supplier_eta_days=3),
    dict(sku="BIF-156",    lens_type="Bifocal",       lens_index="1.56", qty_in_stock=18, min_stock=15, supplier_name="Essilor India", supplier_eta_days=3),
    dict(sku="OFF-156",    lens_type="Office",        lens_index="1.56", qty_in_stock=10, min_stock=8,  supplier_name="Zeiss India",   supplier_eta_days=3),
    dict(sku="OFF-160",    lens_type="Office",        lens_index="1.60", qty_in_stock=7,  min_stock=8,  supplier_name="Zeiss India",   supplier_eta_days=3),
]

COATING_STOCK = [
    dict(coating_name="Anti-Reflective", qty_in_stock=180, min_stock=50, unit="units", supplier_eta="In stock"),
    dict(coating_name="Blue Cut",        qty_in_stock=140, min_stock=50, unit="units", supplier_eta="In stock"),
    dict(coating_name="Photochromic",    qty_in_stock=22,  min_stock=30, unit="rolls", supplier_eta="3 days (ordered)"),
    dict(coating_name="Polarised",       qty_in_stock=15,  min_stock=20, unit="rolls", supplier_eta="5 days (low)"),
    dict(coating_name="Plain",           qty_in_stock=999, min_stock=0,  unit="units", supplier_eta="Always available"),
]

SAMPLE_ORDERS = [
    dict(customer_name="Priya Mehta",   customer_phone="+91 9820123456", store_location="Bandra",
         frame_reference="RB3025 Black", lens_type=LensType.PROGRESSIVE, lens_index=LensIndex.I167,
         coating=Coating.AR, r_sph="-2.50", l_sph="-2.25", sla_days=7,
         stage=OrderStage.QC_CHECK, placed_at=dt(8), inv_status=InvStatus.IN_HOUSE, ai_risk="high"),
    dict(customer_name="Arjun Singh",   customer_phone="+91 9876543210", store_location="Andheri",
         frame_reference="Oakley Fuel", lens_type=LensType.SINGLE_VISION, lens_index=LensIndex.I160,
         coating=Coating.BLUE_CUT, r_sph="-1.00", l_sph="-1.25", sla_days=3,
         stage=OrderStage.DISPATCH, placed_at=dt(3), inv_status=InvStatus.IN_HOUSE, ai_risk="low"),
    dict(customer_name="Divya Nair",    customer_phone="+91 9741234567", store_location="Powai",
         frame_reference="Titan T-Rex", lens_type=LensType.SINGLE_VISION, lens_index=LensIndex.I167,
         coating=Coating.PHOTOCHROMIC, r_sph="-3.50", l_sph="-3.75", sla_days=3,
         stage=OrderStage.LAB_CUTTING, placed_at=dt(5), inv_status=InvStatus.SOURCED, ai_risk="high"),
    dict(customer_name="Rahul Sharma",  customer_phone="+91 9012345678", store_location="Online",
         frame_reference="Lacoste L2812", lens_type=LensType.BIFOCAL, lens_index=LensIndex.I156,
         coating=Coating.AR, r_sph="+1.50", l_sph="+1.25", sla_days=5,
         stage=OrderStage.COATING, placed_at=dt(4), inv_status=InvStatus.IN_HOUSE, ai_risk="medium"),
    dict(customer_name="Sneha Joshi",   customer_phone="+91 9823456781", store_location="Bandra",
         frame_reference="RayBan RX5228", lens_type=LensType.OFFICE, lens_index=LensIndex.I160,
         coating=Coating.BLUE_CUT, r_sph="-0.50", l_sph="-0.75", sla_days=4,
         stage=OrderStage.EDGING, placed_at=dt(2), inv_status=InvStatus.IN_HOUSE, ai_risk="low"),
    dict(customer_name="Karan Kapoor",  customer_phone="+91 9765432109", store_location="Andheri",
         frame_reference="Zara ZA4039", lens_type=LensType.BIFOCAL, lens_index=LensIndex.I150,
         coating=Coating.AR, r_sph="+2.00", l_sph="+2.25", sla_days=5,
         stage=OrderStage.COATING, placed_at=dt(6), inv_status=InvStatus.IN_HOUSE, ai_risk="medium"),
    dict(customer_name="Anita Roy",     customer_phone="+91 9345678901", store_location="Powai",
         frame_reference="Gucci GG0396", lens_type=LensType.PROGRESSIVE, lens_index=LensIndex.I174,
         coating=Coating.POLARISED, r_sph="-1.75", l_sph="-2.00", sla_days=7,
         stage=OrderStage.DELIVERED, placed_at=dt(10), inv_status=InvStatus.IN_HOUSE, ai_risk="low"),
    dict(customer_name="Vikram Bose",   customer_phone="+91 9812345670", store_location="Bandra",
         frame_reference="Titan Steelman", lens_type=LensType.SINGLE_VISION, lens_index=LensIndex.I156,
         coating=Coating.PLAIN, r_sph="+0.75", l_sph="+1.00", sla_days=3,
         stage=OrderStage.DELIVERED, placed_at=dt(4), inv_status=InvStatus.IN_HOUSE, ai_risk="low"),
    dict(customer_name="Pooja Iyer",    customer_phone="+91 9698765432", store_location="Online",
         frame_reference="Michael Kors", lens_type=LensType.PROGRESSIVE, lens_index=LensIndex.I160,
         coating=Coating.BLUE_CUT, r_sph="-4.00", l_sph="-3.50", sla_days=7,
         stage=OrderStage.QC_CHECK, placed_at=dt(7), inv_status=InvStatus.SOURCED, ai_risk="medium"),
    dict(customer_name="Aman Verma",    customer_phone="+91 9856789012", store_location="Andheri",
         frame_reference="Lenskart Air", lens_type=LensType.OFFICE, lens_index=LensIndex.I167,
         coating=Coating.AR, r_sph="-0.25", l_sph="-0.50", sla_days=4,
         stage=OrderStage.PLACED, placed_at=dt(1), inv_status=InvStatus.IN_HOUSE, ai_risk="low"),
]


async def seed():
    await init_db()
    async with AsyncSessionLocal() as db:
        # Lens inventory
        for item in LENS_SKUS:
            db.add(LensInventory(**item))

        # Coating inventory
        for item in COATING_STOCK:
            db.add(CoatingInventory(**item))

        await db.flush()

        # Orders + initial logs
        for o in SAMPLE_ORDERS:
            ai_risk = o.pop("ai_risk", None)
            order = Order(**o)
            order.ai_risk = ai_risk
            db.add(order)
            await db.flush()
            db.add(OrderStatusLog(
                order_id=order.id, from_stage=None,
                to_stage=OrderStage.PLACED.value, reason="Order placed (seeded)"
            ))
            if order.stage != OrderStage.PLACED:
                db.add(OrderStatusLog(
                    order_id=order.id, from_stage=OrderStage.PLACED.value,
                    to_stage=order.stage.value, reason="Stage advanced (seeded)"
                ))

        await db.commit()
        print(f"✅  Seeded {len(LENS_SKUS)} lens SKUs, {len(COATING_STOCK)} coatings, {len(SAMPLE_ORDERS)} orders.")


if __name__ == "__main__":
    asyncio.run(seed())