"""Migrate old devices data + insert test data for new schema

Revision ID: 004
Revises: 003
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004'
down_revision: Union[str, None] = '003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- Migrate data from old devices table to devices_info ---
    result = conn.execute(sa.text("""
        SELECT device_id, device_type, geozone, street_name,
               latitude, longitude, status, wattage, rated_power,
               controller_id, lamp_id, brightness,
               install_date, last_maintenance, created_at, updated_at
        FROM devices
    """))
    rows = result.fetchall()
    if rows:
        import datetime
        now = datetime.datetime.utcnow()
        for row in rows:
            (device_id, device_type, geozone, street_name,
             latitude, longitude, status, wattage, rated_power,
             controller_id, lamp_id, brightness,
             install_date, last_maintenance, created_at, updated_at) = row

            device_name = f"{device_type}_{device_id}" if device_type else device_id

            conn.execute(
                sa.text("""
                    INSERT INTO devices_info
                        (device_id, device_name, device_type,
                         "businessGroupName", street_name,
                         latitude, longitude, status, wattage, rated_power,
                         controller_id, lamp_id, brightness,
                         install_date, last_maintenance,
                         created_at, updated_at)
                    VALUES
                        (:device_id, :device_name, :device_type,
                         :geozone, :street_name,
                         :latitude, :longitude, :status, :wattage, :rated_power,
                         :controller_id, :lamp_id, :brightness,
                         :install_date, :last_maintenance,
                         :created_at, :updated_at)
                """),
                {
                    "device_id": device_id,
                    "device_name": device_name,
                    "device_type": device_type,
                    "geozone": geozone,
                    "street_name": street_name,
                    "latitude": latitude,
                    "longitude": longitude,
                    "status": status,
                    "wattage": wattage,
                    "rated_power": rated_power,
                    "controller_id": controller_id,
                    "lamp_id": lamp_id,
                    "brightness": brightness,
                    "install_date": install_date,
                    "last_maintenance": last_maintenance,
                    "created_at": created_at or now,
                    "updated_at": updated_at or now,
                }
            )

    # --- Insert groups_info test data (let identity auto-generate id) ---
    groups_data = [
        ('0000', '模拟组', '0000', '模拟组', None),
        ('0001', '分组1', '0000/0001', '模拟组/分组1', '0000'),
        ('0002', '分组2', '0000/0002', '模拟组/分组2', '0000'),
        ('0009', '分组9', '0000/0001/0009', '模拟组/分组1/分组9', '0001'),
        ('0010', '分组10', '0000/0001/0010', '模拟组/分组1/分组10', '0001'),
    ]
    for g in groups_data:
        bgid, bgname, bgidpath, bgnamepath, parent = g
        parent_str = "NULL" if parent is None else f"'{parent}'"
        op.execute(
            f'INSERT INTO groups_info ("businessGroupId", "businessGroupName", '
            f'"businessGroupIdPath", "businessGroupNamePath", "parentGroupId") '
            f"VALUES ('{bgid}', '{bgname}', '{bgidpath}', '{bgnamepath}', {parent_str})"
        )

    # --- Insert devices_fault test data ---
    import datetime
    fault_test_data = [
        {"did": 100000000, "fault": "relay_failure",
         "bgid": "0009", "bgname": "分组9",
         "bgidpath": "0000/0001/0009", "bgnamepath": "模拟组/分组1/分组9",
         "start": datetime.datetime(2026, 4, 1, 18, 54, 0, 123000),
         "end": datetime.datetime(2026, 4, 1, 18, 58, 0, 123000)},
        {"did": 100000001, "fault": "high_temperature",
         "bgid": "0010", "bgname": "分组10",
         "bgidpath": "0000/0001/0010", "bgnamepath": "模拟组/分组1/分组10",
         "start": datetime.datetime(2026, 4, 1, 16, 54, 0, 123000),
         "end": datetime.datetime(2026, 4, 1, 17, 58, 0, 123000)},
        {"did": 100000002, "fault": "high_temperature",
         "bgid": "0009", "bgname": "分组9",
         "bgidpath": "0000/0001/0009", "bgnamepath": "模拟组/分组1/分组9",
         "start": datetime.datetime(2026, 4, 1, 16, 50, 0, 123000),
         "end": datetime.datetime(2026, 4, 1, 17, 58, 0, 123000)},
    ]
    for f in fault_test_data:
        conn.execute(
            sa.text("""
                INSERT INTO devices_fault
                    (device_id, fault,
                     "businessGroupId", "businessGroupName",
                     "businessGroupIdPath", "businessGroupNamePath",
                     start_date, end_date)
                VALUES
                    (:did, :fault,
                     :bgid, :bgname,
                     :bgidpath, :bgnamepath,
                     :start, :end)
            """),
            f,
        )


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text('DELETE FROM devices_info'))
    conn.execute(sa.text('DELETE FROM groups_info'))
    conn.execute(sa.text('DELETE FROM devices_fault'))
