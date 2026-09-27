from fastapi import APIRouter

from app.services.platform_service import PlatformService

router = APIRouter(tags=["platform"])
service = PlatformService()


@router.get("/catalog")
def catalog():
    return service.catalog()


@router.get("/alerts")
def alerts():
    return service.alerts()


@router.get("/oncall")
def oncall():
    return service.oncall()


@router.get("/workflows")
def workflows():
    return service.workflows()


@router.get("/status-page")
def status_page():
    return service.status_page()
