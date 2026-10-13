"""Subscription plan management service."""

from typing import List, Optional
from sqlalchemy.orm import Session

from licensing_service.db.models import Plan


def list_plans(db: Session, active_only: bool = True) -> List[Plan]:
    q = db.query(Plan)
    if active_only:
        q = q.filter(Plan.is_active == True)
    return q.order_by(Plan.price.asc()).all()


def get_plan(db: Session, plan_id: int) -> Optional[Plan]:
    return db.query(Plan).filter(Plan.id == plan_id).first()


def get_plan_by_code(db: Session, plan_code: str) -> Optional[Plan]:
    return db.query(Plan).filter(Plan.plan_code == plan_code.strip().upper()).first()


def create_plan(db: Session, data: dict) -> Plan:
    plan = Plan(
        plan_code=data["plan_code"].strip().upper(),
        name=data["name"].strip(),
        description=data.get("description", "").strip(),
        billing_period=data.get("billing_period", "ANNUAL"),
        price=int(data.get("price", 0)),
        currency=data.get("currency", "INR"),
        maximum_terminals=int(data.get("maximum_terminals", 1)),
        enabled_features=data.get("enabled_features", "ALL"),
        is_active=data.get("is_active", True),
    )
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


def update_plan(db: Session, plan_id: int, data: dict) -> Optional[Plan]:
    plan = get_plan(db, plan_id)
    if not plan:
        return None

    for key, value in data.items():
        if hasattr(plan, key) and value is not None:
            setattr(plan, key, value)

    db.commit()
    db.refresh(plan)
    return plan
