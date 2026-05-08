"""Import API - Excel/CSV data import to database"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Any

router = APIRouter()


class ImportRequest(BaseModel):
    fileName: str
    sheetName: str
    headers: List[str]
    data: List[dict[str, Any]]


@router.post("/excel")
async def import_excel(request: ImportRequest):
    """Import Excel data to database table"""
    import re
    from app.db.session import get_session
    from sqlalchemy import text

    try:
        # Determine table name from filename (without extension)
        table_name = re.sub(r'[^a-zA-Z0-9_]', '_', request.fileName.split('.')[0])
        # Ensure table name is valid SQL identifier
        table_name = f"import_{table_name}".lower()

        async for session in get_session():
            # Check if table exists, if not create it
            check_table = await session.execute(
                text("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :table_name
                """),
                {"table_name": table_name}
            )

            if not check_table.scalar():
                # Create table based on headers
                columns_def = ", ".join([f'"{h}" TEXT' for h in request.headers])
                await session.execute(
                    text(f'CREATE TABLE "{table_name}" ({columns_def})')
                )
                await session.commit()

            # Insert data
            for row in request.data:
                values = [row.get(h) for h in request.headers]
                placeholders = ", ".join([f":{i}" for i in range(len(request.headers))])
                columns = ", ".join([f'"{h}"' for h in request.headers])
                # Convert values to strings to match TEXT columns
                params = {str(i): str(v) if v is not None else None for i, v in enumerate(values)}
                await session.execute(
                    text(f'INSERT INTO "{table_name}" ({columns}) VALUES ({placeholders})'),
                    params
                )
            await session.commit()

        return {
            "success": True,
            "tableName": table_name,
            "rowsImported": len(request.data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))