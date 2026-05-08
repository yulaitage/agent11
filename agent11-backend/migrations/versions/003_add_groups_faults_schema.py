"""Add groups, devices_info, thresholds, faults, consumption tables

Revision ID: 003
Revises: 002
Create Date: 2026-04-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FAULT_ENUM_VALUES = (
    'lamp_power_too_high',
    'lamp_power_too_low',
    'lamp_failure',
    'dimming_failure',
    'current_too_high',
    'current_too_low',
    'power_factor_too_low',
    'high_temperature',
    'relay_failure',
    'control_gear_comm_failure',
    'cycling_failure',
    'supply_loss',
    'lamp_unexpected_on',
    'supply_voltage_too_high',
    'supply_voltage_too_low',
    'group_control_fault',
    'link_control_fault',
    'lux_communication_fault',
    'high_load_power',
    'meter_fault',
    'lux_module_fault',
)


def upgrade() -> None:
    # Create FAULT enum type (raw SQL to handle idempotency)
    # Future: ALTER TABLE devices_fault ALTER COLUMN fault TYPE fault USING fault::fault
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE fault AS ENUM (
                'lamp_power_too_high', 'lamp_power_too_low', 'lamp_failure',
                'dimming_failure', 'current_too_high', 'current_too_low',
                'power_factor_too_low', 'high_temperature', 'relay_failure',
                'control_gear_comm_failure', 'cycling_failure', 'supply_loss',
                'lamp_unexpected_on', 'supply_voltage_too_high', 'supply_voltage_too_low',
                'group_control_fault', 'link_control_fault', 'lux_communication_fault',
                'high_load_power', 'meter_fault', 'lux_module_fault'
            );
        EXCEPTION
            WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # groups_info
    op.create_table(
        'groups_info',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('businessGroupId', sa.String(100), nullable=True),
        sa.Column('businessGroupName', sa.String(100), nullable=True),
        sa.Column('businessGroupIdPath', sa.String(100), nullable=True),
        sa.Column('businessGroupNamePath', sa.String(100), nullable=True),
        sa.Column('parentGroupId', sa.String(100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_groups_info_businessGroupId', 'groups_info', ['businessGroupId'])
    op.create_index('ix_groups_info_parentGroupId', 'groups_info', ['parentGroupId'])

    # devices_info
    op.create_table(
        'devices_info',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('device_id', sa.String(100), unique=True, nullable=False),
        sa.Column('device_name', sa.String(200), nullable=True),
        sa.Column('device_type', sa.String(50), nullable=True),
        sa.Column('businessGroupId', sa.String(100), nullable=True),
        sa.Column('businessGroupName', sa.String(100), nullable=True),
        sa.Column('businessGroupIdPath', sa.String(100), nullable=True),
        sa.Column('businessGroupNamePath', sa.String(100), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('street_name', sa.String(200), nullable=True),
        sa.Column('wattage', sa.Float(), nullable=True),
        sa.Column('rated_power', sa.Float(), nullable=True),
        sa.Column('controller_id', sa.String(100), nullable=True),
        sa.Column('lamp_id', sa.String(100), nullable=True),
        sa.Column('brightness', sa.Float(), nullable=True),
        sa.Column('status', sa.String(20), nullable=True),
        sa.Column('install_date', sa.DateTime(), nullable=True),
        sa.Column('last_maintenance', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_devices_info_device_id', 'devices_info', ['device_id'])
    op.create_index('ix_devices_info_businessGroupId', 'devices_info', ['businessGroupId'])

    # devices_threshold
    op.create_table(
        'devices_threshold',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('device_id', sa.BigInteger(), sa.ForeignKey('devices_info.id'), nullable=False),
        sa.Column('param_name', sa.String(100), nullable=True),
        sa.Column('min_value', sa.Float(), nullable=True),
        sa.Column('max_value', sa.Float(), nullable=True),
        sa.Column('warning_min', sa.Float(), nullable=True),
        sa.Column('warning_max', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_devices_threshold_device_id', 'devices_threshold', ['device_id'])

    # devices_fault
    op.create_table(
        'devices_fault',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(3), nullable=True),
        sa.Column('start_date', sa.DateTime(3), nullable=True),
        sa.Column('end_date', sa.DateTime(3), nullable=True),
        sa.Column('device_id', sa.BigInteger(), nullable=False),
        sa.Column('businessGroupId', sa.String(100), nullable=True),
        sa.Column('businessGroupName', sa.String(100), nullable=True),
        sa.Column('businessGroupIdPath', sa.String(100), nullable=True),
        sa.Column('businessGroupNamePath', sa.String(100), nullable=True),
        sa.Column('fault', sa.String(50), nullable=False),
    )
    op.create_index('ix_devices_fault_device_id', 'devices_fault', ['device_id'])
    op.create_index('ix_devices_fault_fault', 'devices_fault', ['fault'])
    op.create_index('ix_devices_fault_start_date', 'devices_fault', ['start_date'])

    # devices_consumption
    op.create_table(
        'devices_consumption',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('device_id', sa.BigInteger(), nullable=False),
        sa.Column('report_date', sa.Date(), nullable=True),
        sa.Column('businessGroupId', sa.String(100), nullable=True),
        sa.Column('businessGroupName', sa.String(100), nullable=True),
        sa.Column('businessGroupIdPath', sa.String(100), nullable=True),
        sa.Column('businessGroupNamePath', sa.String(100), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
    )
    op.create_index('ix_devices_consumption_device_id', 'devices_consumption', ['device_id'])
    op.create_index('ix_devices_consumption_report_date', 'devices_consumption', ['report_date'])

    # groups_consumption
    op.create_table(
        'groups_consumption',
        sa.Column('id', sa.BigInteger(), sa.Identity(always=True), primary_key=True),
        sa.Column('report_date', sa.Date(), nullable=True),
        sa.Column('businessGroupId', sa.String(100), nullable=True),
        sa.Column('businessGroupName', sa.String(100), nullable=True),
        sa.Column('businessGroupIdPath', sa.String(100), nullable=True),
        sa.Column('businessGroupNamePath', sa.String(100), nullable=True),
        sa.Column('value', sa.Float(), nullable=True),
    )
    op.create_index('ix_groups_consumption_group_id', 'groups_consumption', ['businessGroupId'])
    op.create_index('ix_groups_consumption_report_date', 'groups_consumption', ['report_date'])


def downgrade() -> None:
    op.drop_table('groups_consumption')
    op.drop_table('devices_consumption')
    op.drop_table('devices_fault')
    op.drop_table('devices_threshold')
    op.drop_table('devices_info')
    op.drop_table('groups_info')
    op.execute('DROP TYPE IF EXISTS fault')
