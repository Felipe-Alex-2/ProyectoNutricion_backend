import sys
import os

sys.path.insert(0, os.path.realpath(os.path.dirname(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.database import Base, get_db
from app.main import app
from app.models import User, Role
from app.core.security import get_password_hash, create_access_token

# Test SQLite in-memory / file
engine = create_engine("sqlite:///./test_verify.db", connect_args={"check_same_thread": False})
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
# Crear roles básicos
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
)
db.add_all([admin, nutri, patient])
db.commit()

admin_token = create_access_token(admin.id)
nutri_token = create_access_token(nutri.id)
patient_token = create_access_token(patient.id)

headers_nutri = {"Authorization": f"Bearer {nutri_token}"}
headers_patient = {"Authorization": f"Bearer {patient_token}"}

print("=== 1. TEST RECETA CRUD ===")
recipe_payload = {
    "title": "Bowl Proteico de Quinoa y Salmón",
    "description": "Platillo equilibrado alto en proteínas y omega 3",
    "image_url": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c",
    "calories": 480.0,
    "protein": 38.5,
    "carbohydrates": 45.0,
    "fats": 16.0,
    "fiber": 8.0,
    "servings": 1,
    "prep_time_minutes": 15,
    "cook_time_minutes": 20,
    "difficulty": "Fácil",
    "category": "Almuerzo",
    "ingredients": "120g salmón fresco, 80g quinoa cocida, aguacate, hojas verdes",
    "instructions": "1. Cocinar la quinoa. 2. Sellar el salmón a fuego medio. 3. Emplatar con vegetales y aliño.",
}

res = client.post("/api/v1/recipes", json=recipe_payload, headers=headers_nutri)
assert res.status_code == 201, f"Error {res.status_code}: {res.text}"
recipe_data = res.json()
recipe_id = recipe_data["id"]
print(f"Receta creada exitosamente con ID: {recipe_id}, calorias: {recipe_data['calories']}")

res_list = client.get("/api/v1/recipes", headers=headers_patient)
assert res_list.status_code == 200
assert len(res_list.json()) >= 1
print(f"Listado de recetas verificado: {len(res_list.json())} receta(s) encontradas.")

print("=== 2. TEST ANAMNESIS DEL PACIENTE ===")
anamnesis_payload = {
    "pathologies": "Ninguna diagnosticada",
    "allergies": "Intolerancia a la lactosa",
    "medications": "Ninguno",
    "water_intake_liters": 2.2,
    "alcohol_frequency": "Ocasional",
    "smoke_habit": "No fuma",
    "coffee_cups": 1,
    "sleep_hours": 8.0,
    "physical_activity": "Moderado",
    "digestive_symptoms": "Ninguno",
    "food_preferences": "Prefiere alimentos frescos; no consume cerdo",
    "goal": "Mejorar energía y recomposición corporal",
}

res_an = client.post("/api/v1/clinical/anamnesis/me", json=anamnesis_payload, headers=headers_patient)
assert res_an.status_code == 200, f"Error {res_an.status_code}: {res_an.text}"
print("Anamnesis guardada correctamente por el paciente.")

res_nutri_an = client.get(f"/api/v1/clinical/patients/{patient.id}/anamnesis", headers=headers_nutri)
assert res_nutri_an.status_code == 200
assert res_nutri_an.json()["allergies"] == "Intolerancia a la lactosa"
print(f"Nutricionista consultó exitosamente anamnesis: Alergia = {res_nutri_an.json()['allergies']}")

print("=== 3. TEST HISTORIAL CLÍNICO ===")
clinical_payload = {
    "diagnosis": "Normopeso con necesidad de ajuste en sincronización de comidas",
    "evolution_notes": "Paciente inicia plan con excelente adherencia",
    "clinical_goals": "Mantener 2L de agua diarios y estructurar 4 comidas completas",
}
res_cli = client.post(f"/api/v1/clinical/patients/{patient.id}/records", json=clinical_payload, headers=headers_nutri)
assert res_cli.status_code == 201
print(f"Historial clínico registrado exitosamente. Diagnóstico: {res_cli.json()['diagnosis']}")

res_cli_list = client.get(f"/api/v1/clinical/patients/{patient.id}/records", headers=headers_nutri)
assert res_cli_list.status_code == 200
assert len(res_cli_list.json()) >= 1
print(f"Historial clínico consultado exitosamente: {len(res_cli_list.json())} registro(s).")

# Limpieza
Base.metadata.drop_all(bind=engine)
engine.dispose()
if os.path.exists("test_verify.db"):
    try:
        os.remove("test_verify.db")
    except Exception:
        pass

print("\n[EXITO] TODOS LOS TESTS DE BACKEND PASARON SATISFACTORIAMENTE!")
