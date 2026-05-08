"""Standalone import API server with models schema"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Any
import re
import psycopg2
from contextlib import contextmanager

app = FastAPI(title="Import API")

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": "5433",
    "user": "agent11",
    "password": "agent11_password",
    "database": "agent11db"
}


def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)


class ImportRequest(BaseModel):
    fileName: str
    sheetName: str
    headers: List[str]
    data: List[dict[str, Any]]


@app.post("/api/import/excel")
async def import_excel(request: ImportRequest):
    """Import Excel data to database table - merge with existing data"""
    try:
        table_name = re.sub(r'[^a-zA-Z0-9_]', '_', request.fileName.split('.')[0])
        table_name = f"import_{table_name}".lower()

        conn = get_db_connection()
        cur = conn.cursor()

        # Check if table exists
        cur.execute(
            """SELECT table_name FROM information_schema.tables
               WHERE table_schema = 'public' AND table_name = %s""",
            (table_name,)
        )

        if not cur.fetchone():
            # Create table if not exists
            columns_def = ", ".join([f'"{h}" TEXT' for h in request.headers])
            cur.execute(f'CREATE TABLE "{table_name}" ({columns_def})')
        else:
            # Check if existing columns match - if not, add missing columns
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
            """, (table_name,))
            existing_cols = {row[0] for row in cur.fetchall()}
            for h in request.headers:
                if h not in existing_cols:
                    cur.execute(f'ALTER TABLE "{table_name}" ADD COLUMN "{h}" TEXT')

        # Insert data - use INSERT only (no UPDATE/merge to avoid duplicates)
        columns = ", ".join([f'"{h}"' for h in request.headers])
        placeholders = ", ".join([f"%s" for _ in request.headers])

        for row in request.data:
            values = [row.get(h) for h in request.headers]
            cur.execute(
                f'INSERT INTO "{table_name}" ({columns}) VALUES ({placeholders})',
                values
            )

        conn.commit()
        cur.close()
        conn.close()

        return {
            "success": True,
            "tableName": table_name,
            "rowsImported": len(request.data)
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/models/tables/{table_name}")
async def delete_table(table_name: str):
    """Delete a table from database"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'DROP TABLE IF EXISTS "{table_name}" CASCADE')
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "message": f"Table {table_name} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/models/tables/{table_name}/rows")
async def delete_table_rows(table_name: str):
    """Delete all rows from a table"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'TRUNCATE TABLE "{table_name}" CASCADE')
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "message": f"All rows in {table_name} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models/tables/{table_name}/data")
async def get_table_data(table_name: str, limit: int = 50, offset: int = 0):
    """Return sample rows from a given table."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if table exists
        cur.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        """, (table_name,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"Table '{table_name}' not found")

        # Get columns
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        col_names = [row[0] for row in cur.fetchall()]

        # Fetch rows
        cur.execute(f'SELECT * FROM "{table_name}" LIMIT %s OFFSET %s', (limit, offset))
        rows = []
        for row in cur.fetchall():
            rows.append({col: str(row[i]) if row[i] is not None else None for i, col in enumerate(col_names)})

        # Total count
        cur.execute(f'SELECT count(*) FROM "{table_name}"')
        total = cur.fetchone()[0] or 0

        cur.close()
        conn.close()
        return {
            "table": table_name,
            "columns": col_names,
            "rows": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models/views")
async def get_views():
    """Return all user views with their definitions."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name, view_definition
            FROM information_schema.views
            WHERE table_schema = 'public'
            ORDER BY table_name
        """)
        views = [{"name": row[0], "definition": row[1] or ""} for row in cur.fetchall()]
        cur.close()
        conn.close()
        return {"views": views}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/models/views")
async def create_view(name: str, definition: str):
    """Create a new view."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'CREATE OR REPLACE VIEW "{name}" AS {definition}')
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "name": name}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/models/views/{view_name}")
async def delete_view(view_name: str):
    """Delete a view."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(f'DROP VIEW IF EXISTS "{view_name}" CASCADE')
        conn.commit()
        cur.close()
        conn.close()
        return {"success": True, "message": f"View {view_name} deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models/views/{view_name}/data")
async def get_view_data(view_name: str, limit: int = 50, offset: int = 0):
    """Return sample rows from a view."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Check if view exists
        cur.execute("""
            SELECT table_name FROM information_schema.views
            WHERE table_schema = 'public' AND table_name = %s
        """, (view_name,))
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail=f"View '{view_name}' not found")

        # Get columns
        cur.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (view_name,))
        col_names = [row[0] for row in cur.fetchall()]

        # Fetch rows
        cur.execute(f'SELECT * FROM "{view_name}" LIMIT %s OFFSET %s', (limit, offset))
        rows = []
        for row in cur.fetchall():
            rows.append({col: str(row[i]) if row[i] is not None else None for i, col in enumerate(col_names)})

        # Total count
        cur.execute(f'SELECT count(*) FROM "{view_name}"')
        total = cur.fetchone()[0] or 0

        cur.close()
        conn.close()
        return {
            "table": view_name,
            "columns": col_names,
            "rows": rows,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/models/schema")
async def get_schema():
    """Return all user tables with their columns and a row count."""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Get tables
        cur.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
              AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        table_names = [row[0] for row in cur.fetchall()]

        databases = [{
            "id": "agent11db",
            "name": "agent11db",
            "tables": [],
        }]

        for tbl in table_names:
            # Get columns
            cur.execute("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = %s
                ORDER BY ordinal_position
            """, (tbl,))
            columns = [{
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
            } for row in cur.fetchall()]

            # Get row count
            cur.execute(f'SELECT count(*) FROM "{tbl}"')
            row_count = cur.fetchone()[0] or 0

            databases[0]["tables"].append({
                "name": tbl,
                "columns": [c["name"] for c in columns],
                "columns_detail": columns,
                "row_count": row_count,
            })

        cur.close()
        conn.close()
        return {"databases": databases}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/health/")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=3001)