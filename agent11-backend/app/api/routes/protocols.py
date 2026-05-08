"""Protocol specs API (JSON/YAML) + raw payload decoding"""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.protocols.spec import ProtocolSpec
from app.protocols.parser import parse_raw_data

router = APIRouter()


def _protocols_dir() -> Path:
    # Store under backend working directory ./data/protocols
    p = Path("data") / "protocols"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _load_spec_from_bytes(raw: bytes) -> ProtocolSpec:
    text = raw.decode("utf-8", errors="replace")
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        try:
            obj = yaml.safe_load(text)
        except Exception as e:  # noqa: BLE001
            raise ValueError("Invalid JSON/YAML protocol spec") from e
    if not isinstance(obj, dict):
        raise ValueError("Protocol spec root must be an object")
    return ProtocolSpec.model_validate(obj)


class ParseRequest(BaseModel):
    protocol_id: str
    raw_data: str


@router.get("/")
async def list_protocols():
    items = []
    for fp in sorted(_protocols_dir().glob("*.json")):
        items.append({"protocol_id": fp.stem, "filename": fp.name})
    return {"protocols": items, "total": len(items)}


@router.get("/{protocol_id}")
async def get_protocol(protocol_id: str):
    fp = _protocols_dir() / f"{protocol_id}.json"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Protocol not found")
    data = json.loads(fp.read_text(encoding="utf-8"))
    return {"protocol": data}


@router.post("/upload")
async def upload_protocol(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        spec = _load_spec_from_bytes(raw)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    fp = _protocols_dir() / f"{spec.protocol_id}.json"
    fp.write_text(spec.model_dump_json(indent=2, ensure_ascii=False), encoding="utf-8")
    return {"success": True, "protocol_id": spec.protocol_id, "filename": fp.name}


@router.post("/parse")
async def parse_payload(request: ParseRequest):
    fp = _protocols_dir() / f"{request.protocol_id}.json"
    if not fp.exists():
        raise HTTPException(status_code=404, detail="Protocol not found")
    spec = ProtocolSpec.model_validate(json.loads(fp.read_text(encoding="utf-8")))
    try:
        decoded = parse_raw_data(request.raw_data, spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Also provide a simple table form for UI reuse.
    headers = ["字段", "值", "单位"]
    rows = []
    for f in spec.fields:
        val = decoded.get(f.name)
        rows.append([f.name, str(val), f.unit or ""])

    return {
        "success": True,
        "data": {
            "decoded": decoded,
            "table": {"headers": headers, "rows": rows, "total": len(rows)},
        },
    }

