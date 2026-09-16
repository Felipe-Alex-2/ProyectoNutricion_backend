import sys
import os

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import User, Role, Recipe
from app.core.security import get_password_hash, create_access_token

# Test SQLite in-memory / file
engine = create_engine("sqlite:///./test_new_features.db", connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)

def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

db = TestingSessionLocal()
# Crear roles
admin_role = Role(id="ADMIN_SAAS", name="Admin SaaS", description="Global", platform="Web")
nutri_role = Role(id="NUTRICIONISTA", name="Nutricionista", description="Nutri", platform="Web")
cliente_role = Role(id="CLIENTE", name="Cliente", description="Paciente", platform="Mobile")
db.add_all([admin_role, nutri_role, cliente_role])
db.commit()

# Crear usuarios
admin = User(
    id="admin-id",
    email="admin@nutrisalud.com",
    hashed_password=get_password_hash("Password123!"),
    full_name="Admin Principal",
    role_id="ADMIN_SAAS",
    is_active=True,
)
nutri = User(
    id="nutri-id",
    email="nutri@nutrisalud.com",
    hashed_password=get_password_hash("Password123!"),
    full_name="Dra. Laura Nutricionista",
    role_id="NUTRICIONISTA",
    is_active=True,
)
patient = User(
    id="patient-id",
    email="paciente@correo.com",
    hashed_password=get_password_hash("Password123!"),
    full_name="Carlos Paciente",
    role_id="CLIENTE",
    is_active=True,
    phone="77889900",
)
db.add_all([admin, nutri, patient])
db.commit()

admin_token = create_access_token(admin.id)
nutri_token = create_access_token(nutri.id)
patient_token = create_access_token(patient.id)

headers_admin = {"Authorization": f"Bearer {admin_token}"}
headers_nutri = {"Authorization": f"Bearer {nutri_token}"}

print("=== 1. TEST VERIFICACIÓN DE LLAVE BITÁCORA ===")
# Probar con contraseña de la cuenta (por defecto sin developer_key_hash)
res_key_ok = client.post("/api/v1/auth/verify-developer-key", json={"developer_key": "Password123!"}, headers=headers_admin)
assert res_key_ok.status_code == 200
assert res_key_ok.json()["valid"] is True
print("✓ Verificación con contraseña original exitosa.")

res_key_fail = client.post("/api/v1/auth/verify-developer-key", json={"developer_key": "ClaveIncorrecta"}, headers=headers_admin)
assert res_key_fail.status_code == 200
assert res_key_fail.json()["valid"] is False
print("✓ Verificación con clave errónea rechazada correctamente (valid=False).")

# Actualizar perfil del admin con clave personalizada
res_update_profile = client.put(
    "/api/v1/users/me",
    json={"full_name": "Admin Principal", "developer_key": "MiLlaveSecreta99"},
    headers=headers_admin,
)
assert res_update_profile.status_code == 200
assert res_update_profile.json()["has_custom_developer_key"] is True
print("✓ Llave personalizada configurada en el perfil del Administrador.")

# Verificar ahora con la nueva llave personalizada
res_key_custom_ok = client.post("/api/v1/auth/verify-developer-key", json={"developer_key": "MiLlaveSecreta99"}, headers=headers_admin)
assert res_key_custom_ok.status_code == 200
assert res_key_custom_ok.json()["valid"] is True
print("✓ Verificación con llave personalizada exitosa.")

# La contraseña anterior ya no debe abrir la bitácora porque hay llave personalizada
res_key_old_fail = client.post("/api/v1/auth/verify-developer-key", json={"developer_key": "Password123!"}, headers=headers_admin)
assert res_key_old_fail.status_code == 200
assert res_key_old_fail.json()["valid"] is False
print("✓ Acceso con contraseña original bloqueado tras personalizar llave.")

print("=== 2. TEST MÓDULO DE PACIENTES/CLIENTES ===")
res_patients = client.get("/api/v1/users/patients", headers=headers_admin)
assert res_patients.status_code == 200
patients_data = res_patients.json()
assert len(patients_data) == 1
assert patients_data[0]["email"] == "paciente@correo.com"
print(f"✓ Listado de pacientes retornado: {len(patients_data)} paciente(s).")

# Editar paciente
res_edit_patient = client.put(
    f"/api/v1/users/patients/{patient.id}",
    json={"full_name": "Carlos Paciente Actualizado", "phone": "70011223", "is_active": True},
    headers=headers_admin,
)
assert res_edit_patient.status_code == 200
assert res_edit_patient.json()["full_name"] == "Carlos Paciente Actualizado"
print("✓ Edición de datos del paciente exitosa.")

print("=== 3. TEST ASISTENTE IA DE RECOMENDACIONES NUTRICIONALES ===")
# Crear recetas para evaluar
receta_saludable = Recipe(
    id="rec-1",
    title="Ensalada Mediterránea con Salmón",
    description="Rica en omega 3 y vegetales frescos",
    category="Almuerzo",
    calories=420.0,
    protein=35.0,
    carbohydrates=20.0,
    fats=12.0,
    fiber=7.0,
    ingredients="Salmón, lechuga, espinaca, aceite de oliva, limón",
    instructions="Mezclar y servir",
    created_by=nutri.id,
    is_active=True,
)
receta_lacteos = Recipe(
    id="rec-2",
    title="Pasta Carbonara con Crema y Queso",
    description="Platillo con queso parmesano y crema de leche",
    category="Almuerzo",
    calories=750.0,
    protein=22.0,
    carbohydrates=85.0,
    fats=35.0,
    fiber=2.0,
    ingredients="Pasta de trigo, crema de leche entera, queso parmesano, tocino",
    instructions="Cocinar pasta y añadir salsa de crema",
    created_by=nutri.id,
    is_active=True,
)
db.add_all([receta_saludable, receta_lacteos])
db.commit()

# Crear anamnesis con alergia a lácteos y objetivo de pérdida de peso
anamnesis_payload = {
    "pathologies": "Ninguna",
    "allergies": "Alérgica a la leche, crema de leche y queso",
    "medications": "Ninguno",
    "water_intake_liters": 2.5,
    "sleep_hours": 7.5,
    "physical_activity": "Moderado",
    "goal": "Bajar grasa y perder peso",
}
res_an = client.post("/api/v1/clinical/anamnesis/me", json=anamnesis_payload, headers={"Authorization": f"Bearer {patient_token}"})
assert res_an.status_code == 200

# Consultar motor IA de recomendaciones
res_ai = client.get(f"/api/v1/clinical/patients/{patient.id}/ai-recommendations", headers=headers_nutri)
assert res_ai.status_code == 200
ai_data = res_ai.json()
print(f"✓ Recomendaciones IA calculadas para {ai_data['patient_name']}: {len(ai_data['recommendations'])} recetas analizadas.")

# Verificar que la ensalada tenga recomendación alta y la pasta tenga contraindicación o precaución
rec_items = {r["recipe_title"]: r for r in ai_data["recommendations"]}
assert "Ensalada Mediterránea con Salmón" in rec_items
assert "Pasta Carbonara con Crema y Queso" in rec_items

pasta_rec = rec_items["Pasta Carbonara con Crema y Queso"]
print(f"  - Pasta Carbonara evaluada como: {pasta_rec['compatibility_level']} (Puntaje: {pasta_rec['match_score']}%)")
print(f"  - Alertas detectadas: {pasta_rec['warnings']}")
assert pasta_rec["compatibility_level"] in ["PRECAUCION", "CONTRAINDICADA"]

# Asignar receta al paciente con 1 clic
res_assign = client.post(f"/api/v1/recipes/{receta_saludable.id}/assign/{patient.id}", headers=headers_nutri)
assert res_assign.status_code == 200
assert patient.id in res_assign.json()["assigned_patient_ids"]
print(f"✓ Receta prescrita al paciente exitosamente: {res_assign.json()['title']} asignada a {len(res_assign.json()['assigned_patient_ids'])} paciente(s).")

print("=== 4. TEST REPORTES DINÁMICOS (EXCEL Y PDF) ===")
report_query = {
    "entity": "patients",
    "columns": ["full_name", "email", "phone", "is_active", "created_at"],
    "date_from": None,
    "date_to": None,
    "status_filter": "ALL",
}
# Vista previa
res_preview = client.post("/api/v1/reports/query", json=report_query, headers=headers_admin)
assert res_preview.status_code == 200
preview_data = res_preview.json()
assert preview_data["total_rows"] >= 1
print(f"✓ Vista previa de reporte dinámico generada: {preview_data['total_rows']} filas.")

# Exportar a Excel
res_xlsx = client.post("/api/v1/reports/export/excel", json=report_query, headers=headers_admin)
assert res_xlsx.status_code == 200
assert len(res_xlsx.content) > 1000
assert res_xlsx.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
print(f"✓ Exportación Excel (.xlsx) generada exitosamente ({len(res_xlsx.content)} bytes).")

# Exportar a PDF
res_pdf = client.post("/api/v1/reports/export/pdf", json=report_query, headers=headers_admin)
assert res_pdf.status_code == 200
assert len(res_pdf.content) > 1000
assert res_pdf.headers["content-type"] == "application/pdf"
print(f"✓ Exportación PDF generada exitosamente ({len(res_pdf.content)} bytes).")

print("=== 5. TEST MÓDULO DE BACKUP & RESTORE ===")
# Obtener configuración inicial
res_b_settings = client.get("/api/v1/backup/settings", headers=headers_admin)
assert res_b_settings.status_code == 200
print(f"✓ Configuración de backup obtenida: auto_enabled={res_b_settings.json()['auto_backup_enabled']}, freq={res_b_settings.json()['frequency_hours']}h")

# Actualizar configuración de backup
res_update_b = client.put(
    "/api/v1/backup/settings",
    json={"auto_backup_enabled": True, "frequency_hours": 12},
    headers=headers_admin,
)
assert res_update_b.status_code == 200
assert res_update_b.json()["frequency_hours"] == 12
print("✓ Configuración de backup actualizada a 12 horas con auto-backup habilitado.")

# Crear Snapshot manual
res_snapshot = client.post("/api/v1/backup/export", headers=headers_admin)
assert res_snapshot.status_code == 200
snapshot_data = res_snapshot.json()
assert snapshot_data["checksum"] is not None
assert snapshot_data["file_size_bytes"] > 0
print(f"✓ Snapshot manual creado exitosamente: {snapshot_data['filename']} ({snapshot_data['file_size_bytes']} bytes, checksum {snapshot_data['checksum'][:16]}...)")

# Consultar historial
res_hist = client.get("/api/v1/backup/history", headers=headers_admin)
assert res_hist.status_code == 200
assert len(res_hist.json()) >= 1
print(f"✓ Historial de backups consultado: {len(res_hist.json())} copias de seguridad registradas.")

# Descargar archivo de backup
backup_filename = snapshot_data["filename"]
res_dl = client.get(f"/api/v1/backup/download/{backup_filename}", headers=headers_admin)
assert res_dl.status_code == 200
assert len(res_dl.content) > 100
print(f"✓ Descarga de snapshot verificada ({len(res_dl.content)} bytes de JSON).")

# Limpieza
Base.metadata.drop_all(bind=engine)
engine.dispose()
if os.path.exists("test_new_features.db"):
    try:
        os.remove("test_new_features.db")
    except Exception:
        pass

print("\n=======================================================")
print("★ TODOS LOS 5 MÓDULOS NUEVOS SUPERARON EL 100% DE TESTS!")
print("=======================================================")
