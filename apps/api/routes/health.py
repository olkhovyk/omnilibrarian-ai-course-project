from fastapi import APIRouter

from apps.api.readiness import build_readiness_report

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
def ready() -> dict[str, object]:
    return build_readiness_report()
