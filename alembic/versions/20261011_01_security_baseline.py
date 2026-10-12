"""Create missing tables and adopt an existing installation without changing user roles.

Revision ID: 20261011_01
"""
from alembic import op
import sqlalchemy as sa

revision = "20261011_01"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    inspector = sa.inspect(op.get_bind())
    new_tables = set()
    if not inspector.has_table('automation_configs'):
        op.create_table('automation_configs', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('key', sa.String(length=50), nullable=False), sa.Column('is_active', sa.Boolean(), nullable=False), sa.Column('cron_expr', sa.String(length=50), nullable=False), sa.Column('alert_threshold', sa.Integer(), nullable=False), sa.Column('last_run_at', sa.DateTime(), nullable=True), sa.Column('description', sa.String(length=200), nullable=True), sa.PrimaryKeyConstraint('id'))
        new_tables.add('automation_configs')
    if 'automation_configs' in new_tables:
        op.create_index(op.f('ix_automation_configs_id'), 'automation_configs', ['id'], unique=False)
    if 'automation_configs' in new_tables:
        op.create_index(op.f('ix_automation_configs_key'), 'automation_configs', ['key'], unique=True)
    if not inspector.has_table('backup_logs'):
        op.create_table('backup_logs', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('filename', sa.String(length=255), nullable=False), sa.Column('file_size_bytes', sa.Integer(), nullable=False), sa.Column('checksum', sa.String(length=64), nullable=True), sa.Column('backup_type', sa.String(length=50), nullable=False), sa.Column('status', sa.String(length=50), nullable=False), sa.Column('details', sa.Text(), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.PrimaryKeyConstraint('id'))
        new_tables.add('backup_logs')
    if 'backup_logs' in new_tables:
        op.create_index(op.f('ix_backup_logs_tenant_id'), 'backup_logs', ['tenant_id'], unique=False)
    if not inspector.has_table('backup_settings'):
        op.create_table('backup_settings', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('auto_backup_enabled', sa.Boolean(), nullable=False), sa.Column('frequency_hours', sa.Integer(), nullable=False), sa.Column('last_backup_at', sa.DateTime(), nullable=True), sa.Column('retention_days', sa.Integer(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.PrimaryKeyConstraint('id'))
        new_tables.add('backup_settings')
    if 'backup_settings' in new_tables:
        op.create_index(op.f('ix_backup_settings_tenant_id'), 'backup_settings', ['tenant_id'], unique=False)
    if not inspector.has_table('condition_catalog'):
        op.create_table('condition_catalog', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('code', sa.String(length=50), nullable=False), sa.Column('type', sa.String(length=30), nullable=False), sa.Column('name', sa.String(length=100), nullable=False), sa.Column('description', sa.Text(), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.PrimaryKeyConstraint('id'))
        new_tables.add('condition_catalog')
    if 'condition_catalog' in new_tables:
        op.create_index(op.f('ix_condition_catalog_code'), 'condition_catalog', ['code'], unique=True)
    if 'condition_catalog' in new_tables:
        op.create_index(op.f('ix_condition_catalog_id'), 'condition_catalog', ['id'], unique=False)
    if not inspector.has_table('exclusion_rules'):
        op.create_table('exclusion_rules', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('condition_code', sa.String(length=50), nullable=False), sa.Column('excluded_tag', sa.String(length=50), nullable=False), sa.Column('reason', sa.String(length=200), nullable=True), sa.PrimaryKeyConstraint('id'))
        new_tables.add('exclusion_rules')
    if 'exclusion_rules' in new_tables:
        op.create_index(op.f('ix_exclusion_rules_condition_code'), 'exclusion_rules', ['condition_code'], unique=False)
    if 'exclusion_rules' in new_tables:
        op.create_index(op.f('ix_exclusion_rules_excluded_tag'), 'exclusion_rules', ['excluded_tag'], unique=False)
    if 'exclusion_rules' in new_tables:
        op.create_index(op.f('ix_exclusion_rules_id'), 'exclusion_rules', ['id'], unique=False)
    if not inspector.has_table('foods'):
        op.create_table('foods', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('name', sa.String(length=120), nullable=False), sa.Column('category', sa.String(length=50), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.PrimaryKeyConstraint('id'))
        new_tables.add('foods')
    if 'foods' in new_tables:
        op.create_index(op.f('ix_foods_id'), 'foods', ['id'], unique=False)
    if 'foods' in new_tables:
        op.create_index(op.f('ix_foods_name'), 'foods', ['name'], unique=True)
    if not inspector.has_table('habit_parameters'):
        op.create_table('habit_parameters', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('habit', sa.String(length=50), nullable=False), sa.Column('operator', sa.String(length=5), nullable=False), sa.Column('value', sa.Float(), nullable=False), sa.Column('unit', sa.String(length=20), nullable=False), sa.Column('description', sa.String(length=200), nullable=True), sa.PrimaryKeyConstraint('id'))
        new_tables.add('habit_parameters')
    if 'habit_parameters' in new_tables:
        op.create_index(op.f('ix_habit_parameters_habit'), 'habit_parameters', ['habit'], unique=True)
    if 'habit_parameters' in new_tables:
        op.create_index(op.f('ix_habit_parameters_id'), 'habit_parameters', ['id'], unique=False)
    if not inspector.has_table('permissions'):
        op.create_table('permissions', sa.Column('id', sa.String(length=50), nullable=False), sa.Column('name', sa.String(length=100), nullable=False), sa.Column('description', sa.Text(), nullable=False), sa.Column('module', sa.String(length=50), nullable=False), sa.PrimaryKeyConstraint('id'))
        new_tables.add('permissions')
    if not inspector.has_table('roles'):
        op.create_table('roles', sa.Column('id', sa.String(length=50), nullable=False), sa.Column('name', sa.String(length=100), nullable=False), sa.Column('description', sa.Text(), nullable=False), sa.Column('platform', sa.String(length=100), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.PrimaryKeyConstraint('id'))
        new_tables.add('roles')
    if not inspector.has_table('tenants'):
        op.create_table('tenants', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('name', sa.String(length=255), nullable=False), sa.Column('code', sa.String(length=50), nullable=False), sa.Column('phone', sa.String(length=50), nullable=True), sa.Column('email', sa.String(length=255), nullable=True), sa.Column('address', sa.String(length=255), nullable=True), sa.Column('logo_url', sa.String(length=500), nullable=True), sa.Column('description', sa.Text(), nullable=True), sa.Column('is_active', sa.Boolean(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.PrimaryKeyConstraint('id'))
        new_tables.add('tenants')
    if 'tenants' in new_tables:
        op.create_index(op.f('ix_tenants_code'), 'tenants', ['code'], unique=True)
    if 'tenants' in new_tables:
        op.create_index(op.f('ix_tenants_id'), 'tenants', ['id'], unique=False)
    if 'tenants' in new_tables:
        op.create_index(op.f('ix_tenants_name'), 'tenants', ['name'], unique=False)
    if not inspector.has_table('token_blacklist'):
        op.create_table('token_blacklist', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('token', sa.String(length=500), nullable=False), sa.Column('blacklisted_at', sa.DateTime(), nullable=False), sa.Column('expires_at', sa.DateTime(), nullable=True), sa.PrimaryKeyConstraint('id'))
        new_tables.add('token_blacklist')
    if 'token_blacklist' in new_tables:
        op.create_index(op.f('ix_token_blacklist_id'), 'token_blacklist', ['id'], unique=False)
    if 'token_blacklist' in new_tables:
        op.create_index(op.f('ix_token_blacklist_token'), 'token_blacklist', ['token'], unique=True)
    if not inspector.has_table('food_tags'):
        op.create_table('food_tags', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('food_id', sa.String(length=36), nullable=False), sa.Column('tag', sa.String(length=50), nullable=False), sa.ForeignKeyConstraint(['food_id'], ['foods.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('food_tags')
    if 'food_tags' in new_tables:
        op.create_index(op.f('ix_food_tags_food_id'), 'food_tags', ['food_id'], unique=False)
    if 'food_tags' in new_tables:
        op.create_index(op.f('ix_food_tags_id'), 'food_tags', ['id'], unique=False)
    if 'food_tags' in new_tables:
        op.create_index(op.f('ix_food_tags_tag'), 'food_tags', ['tag'], unique=False)
    if not inspector.has_table('role_permissions'):
        op.create_table('role_permissions', sa.Column('role_id', sa.String(length=50), nullable=False), sa.Column('permission_id', sa.String(length=50), nullable=False), sa.ForeignKeyConstraint(['permission_id'], ['permissions.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('role_id', 'permission_id'))
        new_tables.add('role_permissions')
    if not inspector.has_table('users'):
        op.create_table('users', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('email', sa.String(length=255), nullable=False), sa.Column('hashed_password', sa.String(length=255), nullable=False), sa.Column('full_name', sa.String(length=255), nullable=False), sa.Column('phone', sa.String(length=50), nullable=True), sa.Column('role_id', sa.String(length=50), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('session_version', sa.Integer(), server_default='0', nullable=False), sa.Column('is_active', sa.Boolean(), nullable=False), sa.Column('is_verified', sa.Boolean(), nullable=False), sa.Column('developer_key_hash', sa.String(length=255), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['role_id'], ['roles.id'], ondelete='RESTRICT'), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('users')
    if 'users' in new_tables:
        op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    if 'users' in new_tables:
        op.create_index(op.f('ix_users_id'), 'users', ['id'], unique=False)
    if 'users' in new_tables:
        op.create_index(op.f('ix_users_tenant_id'), 'users', ['tenant_id'], unique=False)
    if not inspector.has_table('activity_logs'):
        op.create_table('activity_logs', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('user_id', sa.String(length=36), nullable=True), sa.Column('user_email', sa.String(length=255), nullable=True), sa.Column('user_name', sa.String(length=255), nullable=True), sa.Column('action', sa.String(length=100), nullable=False), sa.Column('description', sa.Text(), nullable=False), sa.Column('category', sa.String(length=50), nullable=False), sa.Column('ip_address', sa.String(length=50), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('activity_logs')
    if 'activity_logs' in new_tables:
        op.create_index(op.f('ix_activity_logs_action'), 'activity_logs', ['action'], unique=False)
    if 'activity_logs' in new_tables:
        op.create_index(op.f('ix_activity_logs_id'), 'activity_logs', ['id'], unique=False)
    if 'activity_logs' in new_tables:
        op.create_index(op.f('ix_activity_logs_user_id'), 'activity_logs', ['user_id'], unique=False)
    if not inspector.has_table('appointments'):
        op.create_table('appointments', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('patient_id', sa.String(length=36), nullable=False), sa.Column('nutritionist_id', sa.String(length=36), nullable=False), sa.Column('scheduled_at', sa.DateTime(), nullable=False), sa.Column('reason', sa.Text(), nullable=True), sa.Column('status', sa.String(length=20), nullable=False), sa.Column('cancellation_reason', sa.Text(), nullable=True), sa.Column('reminder_sent', sa.Boolean(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['nutritionist_id'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('appointments')
    if 'appointments' in new_tables:
        op.create_index(op.f('ix_appointments_id'), 'appointments', ['id'], unique=False)
    if 'appointments' in new_tables:
        op.create_index(op.f('ix_appointments_nutritionist_id'), 'appointments', ['nutritionist_id'], unique=False)
    if 'appointments' in new_tables:
        op.create_index(op.f('ix_appointments_patient_id'), 'appointments', ['patient_id'], unique=False)
    if 'appointments' in new_tables:
        op.create_index(op.f('ix_appointments_tenant_id'), 'appointments', ['tenant_id'], unique=False)
    if not inspector.has_table('chat_messages'):
        op.create_table('chat_messages', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('patient_id', sa.String(length=36), nullable=False), sa.Column('role', sa.String(length=20), nullable=False), sa.Column('content', sa.Text(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('chat_messages')
    if 'chat_messages' in new_tables:
        op.create_index(op.f('ix_chat_messages_id'), 'chat_messages', ['id'], unique=False)
    if 'chat_messages' in new_tables:
        op.create_index(op.f('ix_chat_messages_patient_id'), 'chat_messages', ['patient_id'], unique=False)
    if not inspector.has_table('clinical_records'):
        op.create_table('clinical_records', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('patient_id', sa.String(length=36), nullable=False), sa.Column('nutritionist_id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('diagnosis', sa.Text(), nullable=False), sa.Column('evolution_notes', sa.Text(), nullable=True), sa.Column('clinical_goals', sa.Text(), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['nutritionist_id'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('clinical_records')
    if 'clinical_records' in new_tables:
        op.create_index(op.f('ix_clinical_records_id'), 'clinical_records', ['id'], unique=False)
    if 'clinical_records' in new_tables:
        op.create_index(op.f('ix_clinical_records_nutritionist_id'), 'clinical_records', ['nutritionist_id'], unique=False)
    if 'clinical_records' in new_tables:
        op.create_index(op.f('ix_clinical_records_patient_id'), 'clinical_records', ['patient_id'], unique=False)
    if 'clinical_records' in new_tables:
        op.create_index(op.f('ix_clinical_records_tenant_id'), 'clinical_records', ['tenant_id'], unique=False)
    if not inspector.has_table('device_tokens'):
        op.create_table('device_tokens', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('user_id', sa.String(length=36), nullable=False), sa.Column('token', sa.String(length=500), nullable=False), sa.Column('platform', sa.String(length=20), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('device_tokens')
    if 'device_tokens' in new_tables:
        op.create_index(op.f('ix_device_tokens_id'), 'device_tokens', ['id'], unique=False)
    if 'device_tokens' in new_tables:
        op.create_index(op.f('ix_device_tokens_token'), 'device_tokens', ['token'], unique=True)
    if 'device_tokens' in new_tables:
        op.create_index(op.f('ix_device_tokens_user_id'), 'device_tokens', ['user_id'], unique=False)
    if not inspector.has_table('food_records'):
        op.create_table('food_records', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('patient_id', sa.String(length=36), nullable=False), sa.Column('image_url', sa.String(length=500), nullable=True), sa.Column('result_json', sa.Text(), nullable=False), sa.Column('estimated_calories', sa.Float(), nullable=False), sa.Column('estimated_carbs', sa.Float(), nullable=False), sa.Column('estimated_protein', sa.Float(), nullable=False), sa.Column('estimated_fats', sa.Float(), nullable=False), sa.Column('estimated_fiber', sa.Float(), nullable=False), sa.Column('confidence', sa.String(length=20), nullable=False), sa.Column('notes', sa.Text(), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('food_records')
    if 'food_records' in new_tables:
        op.create_index(op.f('ix_food_records_id'), 'food_records', ['id'], unique=False)
    if 'food_records' in new_tables:
        op.create_index(op.f('ix_food_records_patient_id'), 'food_records', ['patient_id'], unique=False)
    if not inspector.has_table('notifications'):
        op.create_table('notifications', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('user_id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('title', sa.String(length=200), nullable=False), sa.Column('message', sa.Text(), nullable=False), sa.Column('type', sa.String(length=50), nullable=False), sa.Column('reference_id', sa.String(length=36), nullable=True), sa.Column('is_read', sa.Boolean(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'), sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('notifications')
    if 'notifications' in new_tables:
        op.create_index(op.f('ix_notifications_id'), 'notifications', ['id'], unique=False)
    if 'notifications' in new_tables:
        op.create_index(op.f('ix_notifications_tenant_id'), 'notifications', ['tenant_id'], unique=False)
    if 'notifications' in new_tables:
        op.create_index(op.f('ix_notifications_user_id'), 'notifications', ['user_id'], unique=False)
    if not inspector.has_table('nutritional_plans'):
        op.create_table('nutritional_plans', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('patient_id', sa.String(length=36), nullable=False), sa.Column('nutritionist_id', sa.String(length=36), nullable=True), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('status', sa.String(length=20), nullable=False), sa.Column('title', sa.String(length=200), nullable=False), sa.Column('goal', sa.String(length=100), nullable=False), sa.Column('daily_calories', sa.Float(), nullable=False), sa.Column('protein_g', sa.Float(), nullable=False), sa.Column('carbs_g', sa.Float(), nullable=False), sa.Column('fats_g', sa.Float(), nullable=False), sa.Column('meals_per_day', sa.Integer(), nullable=False), sa.Column('meals_json', sa.Text(), nullable=False), sa.Column('weekly_menu_json', sa.Text(), nullable=True), sa.Column('clinical_notes', sa.Text(), nullable=True), sa.Column('requires_special_review', sa.Boolean(), nullable=False), sa.Column('approved_at', sa.DateTime(), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['nutritionist_id'], ['users.id'], ondelete='SET NULL'), sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('nutritional_plans')
    if 'nutritional_plans' in new_tables:
        op.create_index(op.f('ix_nutritional_plans_id'), 'nutritional_plans', ['id'], unique=False)
    if 'nutritional_plans' in new_tables:
        op.create_index(op.f('ix_nutritional_plans_nutritionist_id'), 'nutritional_plans', ['nutritionist_id'], unique=False)
    if 'nutritional_plans' in new_tables:
        op.create_index(op.f('ix_nutritional_plans_patient_id'), 'nutritional_plans', ['patient_id'], unique=False)
    if 'nutritional_plans' in new_tables:
        op.create_index(op.f('ix_nutritional_plans_tenant_id'), 'nutritional_plans', ['tenant_id'], unique=False)
    if not inspector.has_table('patient_anamnesis'):
        op.create_table('patient_anamnesis', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('patient_id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('birth_date', sa.DateTime(), nullable=True), sa.Column('gender', sa.String(length=10), nullable=False), sa.Column('weight_kg', sa.Float(), nullable=True), sa.Column('height_cm', sa.Float(), nullable=True), sa.Column('target_weight_kg', sa.Float(), nullable=True), sa.Column('target_weeks', sa.Integer(), nullable=True), sa.Column('pathologies', sa.Text(), nullable=True), sa.Column('allergies', sa.Text(), nullable=True), sa.Column('medications', sa.Text(), nullable=True), sa.Column('other_allergies', sa.Text(), nullable=True), sa.Column('other_pathologies', sa.Text(), nullable=True), sa.Column('water_intake_liters', sa.Float(), nullable=False), sa.Column('alcohol_frequency', sa.String(length=50), nullable=False), sa.Column('smoke_habit', sa.String(length=50), nullable=False), sa.Column('coffee_cups', sa.Integer(), nullable=False), sa.Column('sleep_hours', sa.Float(), nullable=False), sa.Column('fruits_vegetables_daily', sa.Integer(), nullable=True), sa.Column('sugary_drinks_weekly', sa.Integer(), nullable=True), sa.Column('meals_per_day', sa.Integer(), nullable=True), sa.Column('is_pregnant_or_lactating', sa.Boolean(), nullable=True), sa.Column('physical_activity', sa.String(length=50), nullable=False), sa.Column('digestive_symptoms', sa.Text(), nullable=True), sa.Column('food_preferences', sa.Text(), nullable=True), sa.Column('goal', sa.String(length=200), nullable=False), sa.Column('consent_data_processing', sa.Boolean(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('patient_anamnesis')
    if 'patient_anamnesis' in new_tables:
        op.create_index(op.f('ix_patient_anamnesis_id'), 'patient_anamnesis', ['id'], unique=False)
    if 'patient_anamnesis' in new_tables:
        op.create_index(op.f('ix_patient_anamnesis_patient_id'), 'patient_anamnesis', ['patient_id'], unique=True)
    if 'patient_anamnesis' in new_tables:
        op.create_index(op.f('ix_patient_anamnesis_tenant_id'), 'patient_anamnesis', ['tenant_id'], unique=False)
    if not inspector.has_table('patient_nutritionist_links'):
        op.create_table('patient_nutritionist_links', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('nutritionist_id', sa.String(length=36), nullable=False), sa.Column('patient_id', sa.String(length=36), nullable=True), sa.Column('pairing_code', sa.String(length=30), nullable=False), sa.Column('whatsapp_number', sa.String(length=50), nullable=False), sa.Column('status', sa.String(length=20), nullable=False), sa.Column('notes', sa.Text(), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('linked_at', sa.DateTime(), nullable=True), sa.ForeignKeyConstraint(['nutritionist_id'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='SET NULL'), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('patient_nutritionist_links')
    if 'patient_nutritionist_links' in new_tables:
        op.create_index(op.f('ix_patient_nutritionist_links_id'), 'patient_nutritionist_links', ['id'], unique=False)
    if 'patient_nutritionist_links' in new_tables:
        op.create_index(op.f('ix_patient_nutritionist_links_nutritionist_id'), 'patient_nutritionist_links', ['nutritionist_id'], unique=False)
    if 'patient_nutritionist_links' in new_tables:
        op.create_index(op.f('ix_patient_nutritionist_links_pairing_code'), 'patient_nutritionist_links', ['pairing_code'], unique=True)
    if 'patient_nutritionist_links' in new_tables:
        op.create_index(op.f('ix_patient_nutritionist_links_patient_id'), 'patient_nutritionist_links', ['patient_id'], unique=False)
    if not inspector.has_table('payments'):
        op.create_table('payments', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=False), sa.Column('cashier_id', sa.String(length=36), nullable=True), sa.Column('customer_name', sa.String(length=255), nullable=False), sa.Column('customer_email', sa.String(length=255), nullable=True), sa.Column('concept', sa.String(length=255), nullable=False), sa.Column('amount', sa.Float(), nullable=False), sa.Column('currency', sa.String(length=10), nullable=False), sa.Column('status', sa.String(length=50), nullable=False), sa.Column('payment_method', sa.String(length=50), server_default='PAYPAL', nullable=False), sa.Column('paypal_order_id', sa.String(length=100), nullable=True), sa.Column('paypal_capture_id', sa.String(length=100), nullable=True), sa.Column('notes', sa.Text(), nullable=True), sa.Column('created_at', sa.DateTime(timezone=True), nullable=False), sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True), sa.ForeignKeyConstraint(['cashier_id'], ['users.id']), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id']), sa.PrimaryKeyConstraint('id'))
        new_tables.add('payments')
    if 'payments' in new_tables:
        op.create_index(op.f('ix_payments_payment_method'), 'payments', ['payment_method'], unique=False)
    if 'payments' in new_tables:
        op.create_index(op.f('ix_payments_paypal_order_id'), 'payments', ['paypal_order_id'], unique=False)
    if 'payments' in new_tables:
        op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    if 'payments' in new_tables:
        op.create_index(op.f('ix_payments_tenant_id'), 'payments', ['tenant_id'], unique=False)
    if not inspector.has_table('recipes'):
        op.create_table('recipes', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('created_by', sa.String(length=36), nullable=False), sa.Column('title', sa.String(length=200), nullable=False), sa.Column('description', sa.Text(), nullable=True), sa.Column('image_url', sa.String(length=500), nullable=True), sa.Column('calories', sa.Float(), nullable=False), sa.Column('protein', sa.Float(), nullable=False), sa.Column('carbohydrates', sa.Float(), nullable=False), sa.Column('fats', sa.Float(), nullable=False), sa.Column('fiber', sa.Float(), nullable=False), sa.Column('sodium', sa.Float(), nullable=True), sa.Column('servings', sa.Integer(), nullable=False), sa.Column('prep_time_minutes', sa.Integer(), nullable=False), sa.Column('cook_time_minutes', sa.Integer(), nullable=False), sa.Column('difficulty', sa.String(length=50), nullable=False), sa.Column('category', sa.String(length=50), nullable=False), sa.Column('ingredients', sa.Text(), nullable=False), sa.Column('instructions', sa.Text(), nullable=False), sa.Column('is_active', sa.Boolean(), nullable=False), sa.Column('created_at', sa.DateTime(), nullable=False), sa.Column('updated_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='SET NULL'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('recipes')
    if 'recipes' in new_tables:
        op.create_index(op.f('ix_recipes_created_by'), 'recipes', ['created_by'], unique=False)
    if 'recipes' in new_tables:
        op.create_index(op.f('ix_recipes_id'), 'recipes', ['id'], unique=False)
    if 'recipes' in new_tables:
        op.create_index(op.f('ix_recipes_tenant_id'), 'recipes', ['tenant_id'], unique=False)
    if 'recipes' in new_tables:
        op.create_index(op.f('ix_recipes_title'), 'recipes', ['title'], unique=False)
    if not inspector.has_table('subscriptions'):
        op.create_table('subscriptions', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('tenant_id', sa.String(length=36), nullable=True), sa.Column('user_id', sa.String(length=36), nullable=True), sa.Column('plan_name', sa.String(length=50), nullable=False), sa.Column('paypal_order_id', sa.String(length=100), nullable=True), sa.Column('paypal_capture_id', sa.String(length=100), nullable=True), sa.Column('status', sa.String(length=20), nullable=False), sa.Column('amount', sa.Float(), nullable=False), sa.Column('currency', sa.String(length=3), nullable=False), sa.Column('started_at', sa.DateTime(), nullable=True), sa.Column('expires_at', sa.DateTime(), nullable=True), sa.Column('created_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('subscriptions')
    if 'subscriptions' in new_tables:
        op.create_index(op.f('ix_subscriptions_id'), 'subscriptions', ['id'], unique=False)
    if 'subscriptions' in new_tables:
        op.create_index(op.f('ix_subscriptions_paypal_order_id'), 'subscriptions', ['paypal_order_id'], unique=False)
    if 'subscriptions' in new_tables:
        op.create_index(op.f('ix_subscriptions_tenant_id'), 'subscriptions', ['tenant_id'], unique=False)
    if 'subscriptions' in new_tables:
        op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    if not inspector.has_table('anamnesis_conditions'):
        op.create_table('anamnesis_conditions', sa.Column('anamnesis_id', sa.String(length=36), nullable=False), sa.Column('condition_id', sa.String(length=36), nullable=False), sa.ForeignKeyConstraint(['anamnesis_id'], ['patient_anamnesis.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['condition_id'], ['condition_catalog.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('anamnesis_id', 'condition_id'))
        new_tables.add('anamnesis_conditions')
    if not inspector.has_table('recipe_assignments'):
        op.create_table('recipe_assignments', sa.Column('id', sa.String(length=36), nullable=False), sa.Column('recipe_id', sa.String(length=36), nullable=False), sa.Column('patient_id', sa.String(length=36), nullable=False), sa.Column('assigned_at', sa.DateTime(), nullable=False), sa.ForeignKeyConstraint(['patient_id'], ['users.id'], ondelete='CASCADE'), sa.ForeignKeyConstraint(['recipe_id'], ['recipes.id'], ondelete='CASCADE'), sa.PrimaryKeyConstraint('id'))
        new_tables.add('recipe_assignments')
    if 'recipe_assignments' in new_tables:
        op.create_index(op.f('ix_recipe_assignments_id'), 'recipe_assignments', ['id'], unique=False)
    if 'recipe_assignments' in new_tables:
        op.create_index(op.f('ix_recipe_assignments_patient_id'), 'recipe_assignments', ['patient_id'], unique=False)
    if 'recipe_assignments' in new_tables:
        op.create_index(op.f('ix_recipe_assignments_recipe_id'), 'recipe_assignments', ['recipe_id'], unique=False)
    if "session_version" not in {column["name"] for column in sa.inspect(op.get_bind()).get_columns("users")}:
        op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))

def downgrade():
    raise RuntimeError("This adoption baseline cannot be downgraded automatically. Restore a verified database backup.")
