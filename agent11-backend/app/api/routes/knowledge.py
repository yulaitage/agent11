"""知识库 API"""
from fastapi import APIRouter, UploadFile, File, Query, Form
from pydantic import BaseModel
import structlog

from app.knowledge.manager import KnowledgeManager

logger = structlog.get_logger()

router = APIRouter()


class SearchRequest(BaseModel):
    query: str
    limit: int = 5


class FolderRequest(BaseModel):
    name: str
    parentPath: str = ""


km = KnowledgeManager()


@router.get("/")
async def list_knowledge(path: str = Query("")):
    """列出知识库文件"""
    items = await km.list_files(path)
    return {"success": True, "data": items}


@router.get("/{filename:path}")
async def get_file(filename: str):
    """获取文件内容"""
    content = await km.get_file_content(filename)
    if content is None:
        return {"success": False, "error": "File not found"}
    return {
        "success": True,
        "data": {
            "filename": filename.split("/")[-1],
            "path": filename,
            "content": content,
            "isFolder": False,
            "createdAt": None,
            "updatedAt": None,
        }
    }


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    path: str = Form(""),
):
    """上传文件"""
    content = await file.read()
    success, result = await km.upload_file(file.filename, content, path)

    if success:
        return {"success": True, "data": {"filename": result}}
    else:
        return {"success": False, "error": result}


class UpdateFileRequest(BaseModel):
    content: str


@router.put("/{filename:path}")
async def update_file(filename: str, body: UpdateFileRequest):
    """更新文件内容"""
    success = await km.save_file(filename, body.content)
    if success:
        return {"success": True}
    else:
        return {"success": False, "error": "Failed to save file"}


@router.delete("/{filename:path}")
async def delete_file(filename: str):
    """删除文件"""
    success = await km.delete_file(filename)
    if success:
        return {"success": True}
    else:
        return {"success": False, "error": "Failed to delete file"}


@router.post("/search")
async def search_knowledge(request: SearchRequest):
    """语义搜索知识库"""
    results = await km.search(request.query, request.limit)
    return {
        "success": True,
        "data": [
            {
                "filename": r["filename"],
                "content": r["content"],
                "score": r["score"]
            }
            for r in results
        ]
    }


@router.post("/folder")
async def create_folder(request: FolderRequest):
    """创建文件夹"""
    success = await km.create_folder(request.name, request.parentPath)
    if success:
        return {"success": True}
    else:
        return {"success": False, "error": "Failed to create folder"}


@router.delete("/folder/{path:path}")
async def delete_folder(path: str):
    """删除文件夹"""
    success = await km.delete_folder(path)
    if success:
        return {"success": True}
    else:
        return {"success": False, "error": "Failed to delete folder"}