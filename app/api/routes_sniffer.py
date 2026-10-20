from fastapi import APIRouter
from app.engine.network_sniffer import sniffer

router = APIRouter(prefix="/api/sniffer", tags=["CCTV Sniffing & Discovery"])

@router.get("/scan")
def trigger_scan(subnet: str = "127.0.0", start: int = 1, end: int = 25):
    results = sniffer.scan_subnet(subnet, start, end)
    return {
        "status": "COMPLETED",
        "discovered_devices": results,
        "count": len(results)
    }

@router.get("/results")
def get_results():
    return {
        "discovered_devices": sniffer.get_results(),
        "count": len(sniffer.get_results())
    }
