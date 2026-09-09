import pytest
from app.models.user import User
from app.models.rbac import Role
from app.core.security import hash_password, create_access_token


@pytest.fixture
def test_setup(db_session):
    # Crear roles básicos
    admin_role = Role(id="ADMIN_SAAS", name="Admin SaaS", description="Global", platform="Web")
    nutri_role = Role(id="NUTRICIONISTA", name="Nutricionista", description="Nutri", platform="Web")
    cliente_role = Role(id="CLIENTE", name="Cliente", description="Paciente", platform="Mobile")
    db_session.add_all([admin_role, nutri_role, cliente_role])
    db_session.commit()

    # Crear usuarios
    admin = User(
        id="admin-id",
        email="admin@nutrisalud.com",
        hashed_password=hash_password("Password123!"),
        full_name="Admin Principal",
        role_id="ADMIN_SAAS",
        is_active=True,
    )
    nutri = User(
        id="nutri-id",
        email="nutri@nutrisalud.com",
        hashed_password=hash_password("Password123!"),
        full_name="Dra. Laura Nutricionista",
        role_id="NUTRICIONISTA",
        is_active=True,
    )
    patient = User(
        id="patient-id",
        email="paciente@correo.com",
        hashed_password=hash_password("Password123!"),
        full_name="Carlos Paciente",
        role_id="CLIENTE",
        is_active=True,
    )
    db_session.add_all([admin, nutri, patient])
    db_session.commit()

    return {
        "admin_token": create_access_token(data={"sub": admin.id, "email": admin.email}),
        "nutri_token": create_access_token(data={"sub": nutri.id, "email": nutri.email}),
        "patient_token": create_access_token(data={"sub": patient.id, "email": patient.email}),
        "admin": admin,
        "nutri": nutri,
        "patient": patient,
    }


def test_recipe_crud(client, test_setup):
    nutri_token = test_setup["nutri_token"]
    patient_token = test_setup["patient_token"]
    headers_nutri = {"Authorization": f"Bearer {nutri_token}"}
    headers_patient = {"Authorization": f"Bearer {patient_token}"}

    # 1. Crear receta como Nutricionista
    payload = {
        "title": "Ensalada Mediterránea con Salmón",
        "description": "Rica en omega 3 y antioxidantes",
        "image_url": "https://images.unsplash.com/photo-1540420773420-3366772f4999",
        "calories": 420.5,
        "protein": 34.0,
        "carbohydrates": 18.2,
        "fats": 22.0,
        "fiber": 6.5,
        "servings": 2,
        "prep_time_minutes": 20,
        "cook_time_minutes": 15,
        "difficulty": "Fácil",
        "category": "Almuerzo",
        "ingredients": "150g salmón, 100g espinaca, 1 aguacate, aceite de oliva",
        "instructions": "1. Dorar el salmón a la plancha. 2. Mezclar vegetales frescos. 3. Servir y aliñar.",
    }

    res = client.post("/api/v1/recipes", json=payload, headers=headers_nutri)
    assert res.status_code == 201
    recipe_data = res.json()
    assert recipe_data["title"] == payload["title"]
    assert recipe_data["calories"] == 420.5
    assert recipe_data["image_url"] == payload["image_url"]
    recipe_id = recipe_data["id"]

    # 2. Paciente no puede crear recetas
    res_forbidden = client.post("/api/v1/recipes", json=payload, headers=headers_patient)
    assert res_forbidden.status_code == 403

    # 3. Listar recetas
    res_list = client.get("/api/v1/recipes", headers=headers_patient)
    assert res_list.status_code == 200
    recipes = res_list.json()
    assert len(recipes) >= 1
    assert recipes[0]["id"] == recipe_id

    # 4. Actualizar receta
    res_update = client.put(
        f"/api/v1/recipes/{recipe_id}",
        json={"calories": 450.0, "title": "Ensalada Mediterránea Premium"},
        headers=headers_nutri,
    )
    assert res_update.status_code == 200
    assert res_update.json()["calories"] == 450.0
    assert res_update.json()["title"] == "Ensalada Mediterránea Premium"

    # 5. Desactivar receta
    res_delete = client.delete(f"/api/v1/recipes/{recipe_id}", headers=headers_nutri)
    assert res_delete.status_code == 200


def test_anamnesis_and_clinical_record(client, test_setup):
    patient_token = test_setup["patient_token"]
    nutri_token = test_setup["nutri_token"]
    patient = test_setup["patient"]

    headers_patient = {"Authorization": f"Bearer {patient_token}"}
    headers_nutri = {"Authorization": f"Bearer {nutri_token}"}

    # 1. Paciente llena su anamnesis desde el Móvil
    anamnesis_payload = {
        "pathologies": "Ninguna diagnosticada, antecedentes de hipertensión familiar",
        "allergies": "Intolerancia leve a la lactosa",
        "medications": "Complejo multivitamínico",
        "water_intake_liters": 2.5,
        "alcohol_frequency": "Ocasional",
        "smoke_habit": "No fuma",
        "coffee_cups": 2,
        "sleep_hours": 7.5,
        "physical_activity": "Moderado",
        "digestive_symptoms": "Ligera distensión ocasional",
        "food_preferences": "Prefiere pollo, pescado y verduras; no consume berenjenas",
        "goal": "Pérdida de grasa corporal y recomposición",
    }

    res_save = client.post("/api/v1/clinical/anamnesis/me", json=anamnesis_payload, headers=headers_patient)
    assert res_save.status_code == 200
    anamnesis_data = res_save.json()
    assert anamnesis_data["allergies"] == "Intolerancia leve a la lactosa"
    assert anamnesis_data["water_intake_liters"] == 2.5

    # 2. Paciente consulta su propia anamnesis
    res_get_my = client.get("/api/v1/clinical/anamnesis/me", headers=headers_patient)
    assert res_get_my.status_code == 200
    assert res_get_my.json()["goal"] == "Pérdida de grasa corporal y recomposición"

    # 3. Nutricionista consulta la anamnesis del paciente en la Web
    res_nutri_view = client.get(f"/api/v1/clinical/patients/{patient.id}/anamnesis", headers=headers_nutri)
    assert res_nutri_view.status_code == 200
    assert res_nutri_view.json()["allergies"] == "Intolerancia leve a la lactosa"

    # 4. Nutricionista registra diagnóstico clínico y notas de evolución
    record_payload = {
        "diagnosis": "Sobrepeso grado I con perfil lipídico dentro de rangos normales.",
        "evolution_notes": "Paciente motivado para iniciar déficit calórico controlado de 350 kcal.",
        "clinical_goals": "Reducción de 4 kg de masa grasa en 8 semanas priorizando ingesta proteica.",
    }
    res_record = client.post(
        f"/api/v1/clinical/patients/{patient.id}/records",
        json=record_payload,
        headers=headers_nutri,
    )
    assert res_record.status_code == 201
    assert res_record.json()["diagnosis"] == record_payload["diagnosis"]

    # 5. Consultar historial clínico del paciente
    res_list_records = client.get(
        f"/api/v1/clinical/patients/{patient.id}/records",
        headers=headers_nutri,
    )
    assert res_list_records.status_code == 200
    assert len(res_list_records.json()) == 1


def test_recipe_assignments_and_my_plan(client, test_setup):
    nutri_token = test_setup["nutri_token"]
    patient_token = test_setup["patient_token"]
    patient = test_setup["patient"]
    headers_nutri = {"Authorization": f"Bearer {nutri_token}"}
    headers_patient = {"Authorization": f"Bearer {patient_token}"}

    # 1. Nutricionista crea receta asignada al paciente
    payload = {
        "title": "Bowl Proteico de Quinoa",
        "description": "Receta asignada especialmente para Carlos",
        "image_url": "https://images.unsplash.com/photo-1546069901-ba9599a7e63c",
        "calories": 480.0,
        "protein": 32.0,
        "carbohydrates": 45.0,
        "fats": 14.0,
        "fiber": 8.0,
        "servings": 1,
        "prep_time_minutes": 15,
        "cook_time_minutes": 15,
        "difficulty": "Fácil",
        "category": "Almuerzo",
        "ingredients": "100g quinoa cocida, 150g pechuga pollo, vegetales salteados",
        "instructions": "1. Mezclar quinoa con pechuga asada. 2. Añadir vegetales.",
        "assigned_patient_ids": [patient.id],
    }

    res = client.post("/api/v1/recipes", json=payload, headers=headers_nutri)
    assert res.status_code == 201
    recipe_data = res.json()
    assert recipe_data["assigned_patient_ids"] == [patient.id]

    # 2. Paciente consulta su plan desde la App Móvil
    res_plan = client.get("/api/v1/recipes/my-plan", headers=headers_patient)
    assert res_plan.status_code == 200
    my_plan = res_plan.json()
    assert len(my_plan) >= 1
    assert my_plan[0]["title"] == "Bowl Proteico de Quinoa"
    assert my_plan[0]["calories"] == 480.0

    # 3. Nutricionista actualiza la asignación
    recipe_id = recipe_data["id"]
    res_update = client.put(
        f"/api/v1/recipes/{recipe_id}",
        json={"assigned_patient_ids": []},
        headers=headers_nutri,
    )
    assert res_update.status_code == 200
    assert res_update.json()["assigned_patient_ids"] == []

    # 4. Ahora el paciente no tiene recetas asignadas
    res_plan2 = client.get("/api/v1/recipes/my-plan", headers=headers_patient)
    assert res_plan2.status_code == 200
    assert len(res_plan2.json()) == 0
