from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/master-guide-oil-tz")
async def download_master_guide_oil_tz_template() -> FileResponse:
    file_name = "Шаблон_ТЗ_мастер-справка_нефть_предзаполненный.docx"
    candidates = [
        # File bundled into backend image.
        Path("/app/report_of_preset") / file_name,
        # Docker compose mount target (preferred in runtime).
        Path("/report_of_preset") / file_name,
        # Local repo path when running backend without Docker.
        Path(__file__).resolve().parents[3] / "report_of_preset" / file_name,
        # Optional sibling path under backend root.
        Path(__file__).resolve().parents[2] / "report_of_preset" / file_name,
    ]
    file_path = next((path for path in candidates if path.exists()), None)
    if file_path is None:
        raise HTTPException(status_code=404, detail="TZ template file not found")
    return FileResponse(
        path=file_path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=file_name,
    )
