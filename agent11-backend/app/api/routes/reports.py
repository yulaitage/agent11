"""报告 API"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal

router = APIRouter()


class MaintenanceReportRequest(BaseModel):
    report_type: Literal["weekly", "monthly", "annual"]
    geozone: str | None = None
    format: Literal["pdf", "excel", "json"] = "json"


class FlexibleReportRequest(BaseModel):
    query: str
    format: Literal["pdf", "excel", "json"] = "json"


@router.post("/maintenance")
async def generate_maintenance_report(request: MaintenanceReportRequest):
    """生成维护报告"""
    from app.agent.skills.report_skill import ReportSkill
    from app.agent.generator import ConversationContext
    from fastapi.responses import StreamingResponse
    import io

    skill = ReportSkill()

    # 调用报告技能
    result = await skill.execute(
        llm=None,  # 报告生成不需要 LLM
        query=f"生成{request.report_type}报告",
        context=ConversationContext(
            user_id="api",
            chat_id="api",
            skill="maintenance_report",
            query=f"生成{request.report_type}报告",
            context={"geozone": request.geozone, "format": request.format}
        )
    )

    if request.format == "json":
        return result

    title = f"maintenance-{request.report_type}"
    if request.geozone:
        title += f"-zone{request.geozone}"

    if request.format == "pdf":
        # Minimal PDF export from markdown-ish text.
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas

        buf = io.BytesIO()
        c = canvas.Canvas(buf, pagesize=A4)
        width, height = A4
        x = 40
        y = height - 50
        c.setFont("Helvetica", 12)
        c.drawString(x, y, "Agent11 Maintenance Report")
        y -= 24
        c.setFont("Helvetica", 9)
        text = (result.get("answer") or "").replace("\r\n", "\n").split("\n")
        for line in text:
            if y < 60:
                c.showPage()
                y = height - 50
                c.setFont("Helvetica", 9)
            c.drawString(x, y, line[:140])
            y -= 12
        c.showPage()
        c.save()
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{title}.pdf"'},
        )

    if request.format == "excel":
        from openpyxl import Workbook

        wb = Workbook()
        ws = wb.active
        ws.title = "Report"

        ws.append(["Agent11 Maintenance Report"])
        ws.append(["report_type", request.report_type])
        ws.append(["geozone", request.geozone or ""])
        ws.append([])

        data = result.get("data") or {}
        # Prefer structured metrics if present
        if isinstance(data, dict):
            ws.append(["metric", "value"])
            for k, v in data.items():
                if isinstance(v, (dict, list)):
                    continue
                ws.append([k, v])

        ws2 = wb.create_sheet("RawText")
        for line in (result.get("answer") or "").replace("\r\n", "\n").split("\n"):
            ws2.append([line])

        out = io.BytesIO()
        wb.save(out)
        out.seek(0)
        return StreamingResponse(
            out,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{title}.xlsx"'},
        )

    return result


@router.post("/flexible")
async def generate_flexible_report(request: FlexibleReportRequest):
    """生成灵活报告"""
    from app.agent.skills.flexible_skill import FlexibleSkill
    from app.agent.generator import ConversationContext

    skill = FlexibleSkill()

    result = await skill.execute(
        llm=None,
        query=request.query,
        context=ConversationContext(
            user_id="api",
            chat_id="api",
            skill="flexible_report",
            query=request.query,
            context={"format": request.format}
        )
    )

    return result
