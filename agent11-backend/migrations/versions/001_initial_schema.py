"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-04-21

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Devices table
    op.create_table(
        'devices',
        sa.Column('device_id', sa.String(), primary_key=True),
        sa.Column('device_type', sa.String(), nullable=False),
        sa.Column('geozone', sa.String(), index=True),
        sa.Column('street_name', sa.String(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('status', sa.String(), index=True),
        sa.Column('fault_types', sa.String(), nullable=True),
        sa.Column('wattage', sa.Integer(), nullable=True),
        sa.Column('rated_power', sa.Float(), nullable=True),
        sa.Column('controller_id', sa.String(), nullable=True),
        sa.Column('lamp_id', sa.String(), nullable=True),
        sa.Column('brightness', sa.Float(), nullable=True),
        sa.Column('install_date', sa.DateTime(), nullable=True),
        sa.Column('last_maintenance', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_devices_device_type', 'devices', ['device_type'])
    op.create_index('ix_devices_geozone_status', 'devices', ['geozone', 'status'])

    # Device readings table
    op.create_table(
        'device_readings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('device_id', sa.String(), sa.ForeignKey('devices.device_id'), index=True),
        sa.Column('timestamp', sa.DateTime(), index=True),
        sa.Column('voltage', sa.Float(), nullable=True),
        sa.Column('current', sa.Float(), nullable=True),
        sa.Column('power', sa.Float(), nullable=True),
        sa.Column('power_factor', sa.Float(), nullable=True),
        sa.Column('energy_kwh', sa.Float(), nullable=True),
        sa.Column('comm_status', sa.String(), nullable=True),
        sa.Column('raw_data', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_device_readings_device_timestamp', 'device_readings', ['device_id', 'timestamp'])

    # Energy readings table
    op.create_table(
        'energy_readings',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('device_id', sa.String(), index=True),
        sa.Column('geozone', sa.String(), index=True),
        sa.Column('timestamp', sa.DateTime(), index=True),
        sa.Column('period', sa.String(), nullable=True),
        sa.Column('energy_kwh', sa.Float()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_energy_readings_device_timestamp', 'energy_readings', ['device_id', 'timestamp'])
    op.create_index('ix_energy_readings_geozone_timestamp', 'energy_readings', ['geozone', 'timestamp'])

    # Fault records table
    op.create_table(
        'fault_records',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('device_id', sa.String(), index=True),
        sa.Column('geozone', sa.String(), nullable=True, index=True),
        sa.Column('fault_type', sa.String()),
        sa.Column('fault_status', sa.String()),
        sa.Column('detected_at', sa.DateTime(), index=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('response_time_hours', sa.Float(), nullable=True),
        sa.Column('maintenance_action', sa.String(), nullable=True),
        sa.Column('technician', sa.String(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_fault_records_device_detected', 'fault_records', ['device_id', 'detected_at'])
    op.create_index('ix_fault_records_fault_status', 'fault_records', ['fault_status'])

    # Comm logs table
    op.create_table(
        'comm_logs',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('device_id', sa.String(), index=True),
        sa.Column('event_type', sa.String()),
        sa.Column('timestamp', sa.DateTime(), index=True),
        sa.Column('details', postgresql.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_comm_logs_device_timestamp', 'comm_logs', ['device_id', 'timestamp'])
    op.create_index('ix_comm_logs_event_type', 'comm_logs', ['event_type'])

    # Chats table
    op.create_table(
        'chats',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('user_id', sa.String(), index=True),
        sa.Column('chat_title', sa.String()),
        sa.Column('messages', postgresql.JSON()),
        sa.Column('archived', sa.Boolean(), default=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_chats_user_updated', 'chats', ['user_id', 'updated_at'])

    # Eval results table
    op.create_table(
        'eval_results',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('test_case_id', sa.String(), index=True),
        sa.Column('skill', sa.String(), index=True),
        sa.Column('query', sa.Text()),
        sa.Column('overall_score', sa.Float()),
        sa.Column('dimension_scores', postgresql.JSON()),
        sa.Column('latency_ms', sa.Float()),
        sa.Column('passed', sa.Boolean()),
        sa.Column('response_snapshot', postgresql.JSON(), nullable=True),
        sa.Column('error', sa.Text(), nullable=True),
        sa.Column('evaluated_at', sa.DateTime(), server_default=sa.text('now()'), index=True),
    )
    op.create_index('ix_eval_results_skill_evaluated', 'eval_results', ['skill', 'evaluated_at'])

    # Eval test cases table
    op.create_table(
        'eval_test_cases',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('skill', sa.String(), index=True),
        sa.Column('query', sa.Text()),
        sa.Column('context', postgresql.JSON()),
        sa.Column('expected', postgresql.JSON()),
        sa.Column('acceptable_responses', postgresql.JSON()),
        sa.Column('difficulty', sa.String()),
        sa.Column('category', sa.String()),
        sa.Column('is_regression', sa.Boolean(), default=False),
        sa.Column('created_by', sa.String()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
    )
    op.create_index('ix_eval_test_cases_skill_category', 'eval_test_cases', ['skill', 'category'])

    # Metrics history table
    op.create_table(
        'metrics_history',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('timestamp', sa.DateTime(), server_default=sa.text('now()'), index=True),
        sa.Column('skills', postgresql.JSON()),
        sa.Column('knowledge', postgresql.JSON()),
        sa.Column('memory', postgresql.JSON()),
        sa.Column('system', postgresql.JSON()),
    )

    # Skill health table
    op.create_table(
        'skill_health',
        sa.Column('skill', sa.String(), primary_key=True),
        sa.Column('status', sa.String()),
        sa.Column('success_rate', sa.Float()),
        sa.Column('avg_latency_ms', sa.Float()),
        sa.Column('error_rate', sa.Float()),
        sa.Column('issues', postgresql.JSON()),
        sa.Column('recommendations', postgresql.JSON()),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()'), onupdate=sa.text('now()')),
    )

    # Memory palace tables - memory_infra_* tables
    for table_name in [
        'memory_infra_devices', 'memory_infra_geozones', 'memory_infra_systems',
        'memory_infra_protocols'
    ]:
        op.create_table(
            table_name,
            sa.Column('id', sa.String(), primary_key=True),
            sa.Column('entity_id', sa.String(), index=True),
            sa.Column('data', postgresql.JSON()),
            sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
            sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
            sa.Column('archived', sa.Boolean(), default=False),
            sa.Column('archived_at', sa.DateTime(), nullable=True),
        )

    # memory_convers_episodes - has summary and learned_facts instead of data
    op.create_table(
        'memory_convers_episodes',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('entity_id', sa.String(), index=True),
        sa.Column('summary', postgresql.JSON()),
        sa.Column('learned_facts', postgresql.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('archived', sa.Boolean(), default=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
    )

    # memory_convers_sessions - has summary and data
    op.create_table(
        'memory_convers_sessions',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('entity_id', sa.String(), index=True),
        sa.Column('summary', postgresql.JSON()),
        sa.Column('data', postgresql.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('archived', sa.Boolean(), default=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
    )

    # memory_convers_preferences - has preference_type and data
    op.create_table(
        'memory_convers_preferences',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('entity_id', sa.String(), index=True),
        sa.Column('preference_type', sa.String()),
        sa.Column('data', postgresql.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('archived', sa.Boolean(), default=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
    )

    # memory_learning_patterns - has pattern_type and pattern_data
    op.create_table(
        'memory_learning_patterns',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('entity_id', sa.String(), index=True),
        sa.Column('pattern_type', sa.String()),
        sa.Column('pattern_data', postgresql.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('archived', sa.Boolean(), default=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
    )

    # memory_learning_relationships - has source_entity, target_entity, relationship_type, data
    op.create_table(
        'memory_learning_relationships',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('entity_id', sa.String(), index=True),
        sa.Column('source_entity', sa.String()),
        sa.Column('target_entity', sa.String()),
        sa.Column('relationship_type', sa.String()),
        sa.Column('data', postgresql.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('archived', sa.Boolean(), default=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
    )

    # memory_learning_insights - has insight_type and data
    op.create_table(
        'memory_learning_insights',
        sa.Column('id', sa.String(), primary_key=True),
        sa.Column('entity_id', sa.String(), index=True),
        sa.Column('insight_type', sa.String()),
        sa.Column('data', postgresql.JSON()),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.text('now()')),
        sa.Column('archived', sa.Boolean(), default=False),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    # Drop memory palace tables
    for table_name in [
        'memory_infra_devices', 'memory_infra_geozones', 'memory_infra_systems',
        'memory_infra_protocols', 'memory_convers_episodes',
        'memory_convers_sessions', 'memory_convers_preferences',
        'memory_learning_patterns', 'memory_learning_relationships',
        'memory_learning_insights'
    ]:
        op.drop_table(table_name)

    # Drop main tables
    op.drop_table('skill_health')
    op.drop_table('metrics_history')
    op.drop_table('eval_test_cases')
    op.drop_table('eval_results')
    op.drop_table('chats')
    op.drop_table('comm_logs')
    op.drop_table('fault_records')
    op.drop_table('energy_readings')
    op.drop_table('device_readings')
    op.drop_table('devices')
