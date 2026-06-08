"""离线地图瓦片服务"""
import os
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

TILES_DIR = os.environ.get("TILES_DIR", "/home/ubuntu/agent11-backend/data/tiles")


@router.get("/tiles/{z}/{x}/{y}.png")
async def get_tile(z: int, x: int, y: int):
    """提供本地存储的离线地图瓦片"""
    tile_path = os.path.join(TILES_DIR, str(z), str(x), f"{y}.png")
    if os.path.exists(tile_path):
        return FileResponse(tile_path, media_type="image/png")
    # Try .webp format
    tile_path_webp = os.path.join(TILES_DIR, str(z), str(x), f"{y}.webp")
    if os.path.exists(tile_path_webp):
        return FileResponse(tile_path_webp, media_type="image/webp")
    raise HTTPException(status_code=404, detail="Tile not found")
