"""Modeling API — reflect database schema and browse table data"""
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import text
import structlog

from app.db.session import get_session

logger = structlog.get_logger()
router = APIRouter()


@router.get("/schema")
async def get_schema():
    """Return all user tables with their columns and a row count."""
    async for session in get_session():
        # 1) tables
        table_result = await session.execute(
            text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                  AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)
        )
        table_names = [row[0] for row in table_result]

        # 2) columns + row count per table
        databases = [
            {
                "id": "agent11db",
                "name": "agent11db",
                "tables": [],
            }
        ]

        for tbl in table_names:
            col_result = await session.execute(
                text("""
                    SELECT column_name, data_type, is_nullable
                    FROM information_schema.columns
                    WHERE table_schema = 'public' AND table_name = :t
                    ORDER BY ordinal_position
                """),
                {"t": tbl},
            )
            columns = [
                {
                    "name": row[0],
                    "type": row[1],
                    "nullable": row[2] == "YES",
                }
                for row in col_result
            ]

            count_result = await session.execute(
                text(f'SELECT count(*) FROM public."{tbl}"')
            )
            row_count = count_result.scalar() or 0

            databases[0]["tables"].append({
                "name": tbl,
                "columns": [c["name"] for c in columns],
                "columns_detail": columns,
                "row_count": row_count,
            })

        return {"databases": databases}


@router.get("/tables/{table_name}/data")
async def get_table_data(
    table_name: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Return sample rows from a given table."""
    async for session in get_session():
        # verify table exists
        check = await session.execute(
            text("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public' AND table_name = :t
            """),
            {"t": table_name},
        )
        if not check.scalar():
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # get columns first
        col_result = await session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :t
                ORDER BY ordinal_position
            """),
            {"t": table_name},
        )
        col_names = [row[0] for row in col_result]

        # fetch rows
        rows_result = await session.execute(
            text(f'SELECT * FROM public."{table_name}" LIMIT :lim OFFSET :off'),
            {"lim": limit, "off": offset},
        )

        rows = []
        for row in rows_result:
            rows.append({col: str(row[i]) if row[i] is not None else None for i, col in enumerate(col_names)})

        # total count
        count_result = await session.execute(
            text(f'SELECT count(*) FROM public."{table_name}"')
        )

        return {
            "table": table_name,
            "columns": col_names,
            "rows": rows,
            "total": count_result.scalar() or 0,
            "limit": limit,
            "offset": offset,
        }


@router.get("/views")
async def get_views():
    """Return all user views with their definitions."""
    async for session in get_session():
        result = await session.execute(
            text("""
                SELECT table_name, view_definition
                FROM information_schema.views
                WHERE table_schema = 'public'
                ORDER BY table_name
            """)
        )
        views = [{"name": row[0], "definition": row[1] or ""} for row in result]
        return {"views": views}


@router.delete("/tables/{table_name}")
async def delete_table(table_name: str):
    """Delete a table from database."""
    async for session in get_session():
        await session.execute(text(f'DROP TABLE IF EXISTS "{table_name}" CASCADE'))
        await session.commit()
        return {"success": True, "message": f"Table {table_name} deleted"}


@router.delete("/tables/{table_name}/rows")
async def delete_table_rows(table_name: str):
    """Delete all rows from a table."""
    async for session in get_session():
        await session.execute(text(f'TRUNCATE TABLE "{table_name}" CASCADE'))
        await session.commit()
        return {"success": True, "message": f"All rows in {table_name} deleted"}


@router.post("/views")
async def create_view(name: str, definition: str):
    """Create a new view."""
    async for session in get_session():
        await session.execute(
            text(f'CREATE OR REPLACE VIEW "{name}" AS {definition}')
        )
        await session.commit()
        return {"success": True, "name": name}


@router.delete("/views/{view_name}")
async def delete_view(view_name: str):
    """Delete a view."""
    async for session in get_session():
        await session.execute(text(f'DROP VIEW IF EXISTS "{view_name}" CASCADE'))
        await session.commit()
        return {"success": True, "message": f"View {view_name} deleted"}


@router.get("/views/{view_name}/data")
async def get_view_data(
    view_name: str,
    limit: int = Query(50, ge=1, le=1000),
    offset: int = Query(0, ge=0),
):
    """Return sample rows from a view."""
    async for session in get_session():
        # verify view exists
        check = await session.execute(
            text("""
                SELECT table_name FROM information_schema.views
                WHERE table_schema = 'public' AND table_name = :v
            """),
            {"v": view_name},
        )
        if not check.scalar():
            raise HTTPException(status_code=404, detail=f"View '{view_name}' not found")

        # get columns
        col_result = await session.execute(
            text("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :v
                ORDER BY ordinal_position
            """),
            {"v": view_name},
        )
        col_names = [row[0] for row in col_result]

        # fetch rows
        rows_result = await session.execute(
            text(f'SELECT * FROM public."{view_name}" LIMIT :lim OFFSET :off'),
            {"lim": limit, "off": offset},
        )
        rows = []
        for row in rows_result:
            rows.append({col: str(row[i]) if row[i] is not None else None for i, col in enumerate(col_names)})

        # total count
        count_result = await session.execute(
            text(f'SELECT count(*) FROM public."{view_name}"')
        )
        return {
            "table": view_name,
            "columns": col_names,
            "rows": rows,
            "total": count_result.scalar() or 0,
            "limit": limit,
            "offset": offset,
        }
