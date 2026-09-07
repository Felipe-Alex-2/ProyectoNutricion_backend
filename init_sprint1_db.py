import sys
from sqlalchemy import text, inspect
from app.database import get_engine, Base, get_session_local
from app.models.tenant import Tenant
from app.models.rbac import Role, Permission, RolePermission
from app.models.user import User
from app.models.patient_link import PatientNutritionistLink


def init_db():
    print("Running database initialization and migration...")
    import time
    eng = get_engine()
    for attempt in range(1, 11):
        try:
            with eng.connect() as conn:
                conn.execute(text("SELECT 1"))
                print("Database connection successfully established.")
                break
        except Exception as e:
            if attempt == 10:
                print(f"Failed to connect to database after 10 attempts: {e}")
                raise e
            print(f"Waiting for database to be ready (attempt {attempt}/10)...")
            time.sleep(2)

    # 1. Create all non-existing tables
    Base.metadata.create_all(bind=eng)
    print("Base metadata create_all completed.")

    # 2. Check and alter 'users' table columns if needed
    insp = inspect(eng)
    if 'users' in insp.get_table_names():
        existing_user_cols = [c['name'] for c in insp.get_columns('users')]
        with eng.connect() as conn:
            if 'phone' not in existing_user_cols:
                print("Adding column 'phone' to 'users' table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN phone VARCHAR(50);"))
                conn.commit()
            if 'role_id' not in existing_user_cols:
                print("Adding column 'role_id' to 'users' table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN role_id VARCHAR(50) DEFAULT 'CLIENTE';"))
                conn.commit()
            if 'tenant_id' not in existing_user_cols:
                print("Adding column 'tenant_id' to 'users' table...")
                conn.execute(text("ALTER TABLE users ADD COLUMN tenant_id VARCHAR(36);"))
                conn.commit()

    db = get_session_local()()
    try:
        # 3. Seed Roles
        roles_data = [
            {
                "id": "ADMIN_SAAS",
                "name": "Administrador SaaS (Admin Global)",
                "description": "Nivel más alto con control total de la plataforma SaaS y gestión de todas las clínicas.",
                "platform": "Web",
            },
            {
                "id": "ADMIN_ORGANIZATION",
                "name": "Administrador de Organización (Admin Local)",
                "description": "Gestiona una clínica o centro de nutrición específico y a sus usuarios asociados.",
                "platform": "Web",
            },
            {
                "id": "NUTRICIONISTA",
                "name": "Nutricionista",
                "description": "Especialista enfocado en la gestión clínica, planes de alimentación y seguimiento.",
                "platform": "Web",
            },
            {
                "id": "CLIENTE",
                "name": "Cliente (Paciente)",
                "description": "Usuario final. Se vincula a su nutricionista con código, consulta su plan, comidas y citas.",
                "platform": "Móvil / Web",
            },
        ]

        for r_data in roles_data:
            role = db.query(Role).filter_by(id=r_data["id"]).first()
            if not role:
                role = Role(**r_data)
                db.add(role)
            else:
                role.name = r_data["name"]
                role.description = r_data["description"]
                role.platform = r_data["platform"]
        db.commit()
        print("Roles seeded successfully.")

        # 4. Seed Permissions
        permissions_data = [
            {"id": "tenants:manage", "name": "Gestionar Tenants", "description": "Crear, editar y desactivar clínicas/organizaciones", "module": "SaaS"},
            {"id": "roles:manage", "name": "Gestionar Roles", "description": "Ver y configurar matriz de permisos y roles", "module": "SaaS"},
            {"id": "users:manage_all", "name": "Gestionar Todos los Usuarios", "description": "Administrar usuarios globales de la plataforma", "module": "SaaS"},
            {"id": "users:manage_org", "name": "Gestionar Usuarios de Organización", "description": "Administrar nutricionistas y pacientes de su clínica", "module": "Organización"},
            {"id": "clinical:manage", "name": "Gestión Clínica", "description": "Crear planes nutricionales, dietas y seguimiento", "module": "Clínica"},
            {"id": "patient:link", "name": "Vincular Pacientes", "description": "Generar códigos WhatsApp y emparejar pacientes", "module": "Clínica"},
            {"id": "patient:self_progress", "name": "Progreso Personal", "description": "Consultar plan propio, registrar comidas y citas", "module": "Paciente"},
        ]

        for p_data in permissions_data:
            perm = db.query(Permission).filter_by(id=p_data["id"]).first()
            if not perm:
                perm = Permission(**p_data)
                db.add(perm)
            else:
                perm.name = p_data["name"]
                perm.description = p_data["description"]
                perm.module = p_data["module"]
        db.commit()
        print("Permissions seeded successfully.")

        # 5. Assign Permissions to Roles
        role_perm_map = {
            "ADMIN_SAAS": ["tenants:manage", "roles:manage", "users:manage_all", "users:manage_org", "clinical:manage", "patient:link", "patient:self_progress"],
            "ADMIN_ORGANIZATION": ["users:manage_org", "clinical:manage", "patient:link", "patient:self_progress"],
            "NUTRICIONISTA": ["clinical:manage", "patient:link", "patient:self_progress"],
            "CLIENTE": ["patient:self_progress"],
        }

        for role_id, perm_ids in role_perm_map.items():
            for p_id in perm_ids:
                exists = db.query(RolePermission).filter_by(role_id=role_id, permission_id=p_id).first()
                if not exists:
                    db.add(RolePermission(role_id=role_id, permission_id=p_id))
        db.commit()
        print("Role permissions mapped successfully.")

        # 6. Seed Sample Tenant
        sample_tenant = db.query(Tenant).filter_by(code="VIDASANA").first()
        if not sample_tenant:
            sample_tenant = Tenant(
                name="Clínica NutriSalud Vida Sana",
                code="VIDASANA",
                phone="+591 73683564",
                email="contacto@vidasana.nutricion.com",
                address="Av. San Martín #450, Santa Cruz, Bolivia",
                description="Centro especializado en nutrición clínica y deportiva.",
                is_active=True,
            )
            db.add(sample_tenant)
            db.commit()
            print("Sample tenant 'VIDASANA' created.")

        # 7. Update existing users to ADMIN_SAAS so they have full access
        users = db.query(User).all()
        for u in users:
            if not u.role_id or u.role_id == 'CLIENTE':
                u.role_id = "ADMIN_SAAS"
                u.tenant_id = sample_tenant.id
                u.phone = "+591 73683564"
        db.commit()
        print(f"Updated {len(users)} existing user(s) to ADMIN_SAAS with tenant {sample_tenant.code}.")

    except Exception as e:
        db.rollback()
        print(f"Error during init_db: {e}")
        raise e
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
