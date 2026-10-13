"""Public storefront information router."""

from fastapi import APIRouter
from portal_service.config import settings
from portal_service.schemas import StoreInfoResponse

router = APIRouter(tags=["Store Info"])


@router.get("/store-info", response_model=StoreInfoResponse)
def get_store_info():
    """Return public pharmacy store contact, operating hours, and delivery policies."""
    return StoreInfoResponse(
        store_name=settings.STORE_NAME,
        tagline=settings.STORE_TAGLINE,
        license_number=settings.STORE_LICENSE_NUMBER,
        phone=settings.STORE_PHONE,
        email=settings.STORE_EMAIL,
        address=settings.STORE_ADDRESS,
        operating_hours=settings.OPERATING_HOURS,
        delivery_fee_paise=settings.DELIVERY_FEE_PAISE,
        free_delivery_threshold_paise=settings.FREE_DELIVERY_THRESHOLD_PAISE,
        estimated_delivery_time=settings.ESTIMATED_DELIVERY_TIME,
        estimated_pickup_time=settings.ESTIMATED_PICKUP_TIME,
        rx_policy_notice=settings.RX_POLICY_NOTICE,
    )
