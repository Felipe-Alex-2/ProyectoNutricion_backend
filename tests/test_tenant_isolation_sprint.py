import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.models.tenant import Tenant
from app.models.user import User
from app.models.recipe import Recipe
from app.models.notification import Notification
from app.core.security import get_password_hash, create_access_token


from app.models.rbac import Role


@pytest.fixture
def multi_tenant_setup(db_session):
    # Asegurar roles básicos
    for r_id, r_name in [("ADMIN_SAAS", "Admin"), ("ADMIN_ORGANIZATION", "Admin Org"), ("NUTRICIONISTA", "Nutri"), ("CLIENTE", "Cliente")]:
        existing_role = db_session.query(Role).filter(Role.id == r_id).first()
        if not existing_role:
            db_session.add(Role(id=r_id, name=r_name, description=r_name, platform="Web"))
    db_session.commit()

    # Crear 2 tenants
    t1 = Tenant(id="tenant-clinica-alpha", code="ALPHA", name="Clínica Alpha", is_active=True)
    t2 = Tenant(id="tenant-clinica-beta", code="BETA", name="Clínica Beta", is_active=True)
    db_session.add_all([t1, t2])
    db_session.commit()

    # Nutricionista y Paciente de Alpha
    nutri_a = User(
        id="nutri-alpha-01",
        tenant_id=t1.id,
        email="nutri.alpha@test.com",
        hashed_password=get_password_hash("pass123"),
        full_name="Nutri Alpha",
        role_id="NUTRICIONISTA",
        is_active=True,
    )
    paciente_a = User(
        id="paciente-alpha-01",
        tenant_id=t1.id,
        email="paciente.alpha@test.com",
        hashed_password=get_password_hash("pass123"),
        full_name="Paciente Alpha",
        role_id="CLIENTE",
        is_active=True,
    )

    # Nutricionista y Paciente de Beta
    nutri_b = User(
        id="nutri-beta-01",
        tenant_id=t2.id,
        email="nutri.beta@test.com",
        hashed_password=get_password_hash("pass123"),
        full_name="Nutri Beta",
        role_id="NUTRICIONISTA",
        is_active=True,
    )
    paciente_b = User(
        id="paciente-beta-01",
        tenant_id=t2.id,
        email="paciente.beta@test.com",
        hashed_password=get_password_hash("pass123"),
        full_name="Paciente Beta",
        role_id="CLIENTE",
        is_active=True,
    )

    db_session.add_all([nutri_a, paciente_a, nutri_b, paciente_b])
    db_session.commit()

    # Receta propia de Alpha
    recipe_a = Recipe(
        id="recipe-alpha-01",
        tenant_id=t1.id,
        created_by=nutri_a.id,
        title="Ensalada Quinoa Alpha",
        category="Almuerzo",
        difficulty="Fácil",
        ingredients="Quinoa, tomate, pepino, limón",
        instructions="Cocinar quinoa y mezclar ingredientes.",
        calories=350,
        protein=15,
        carbohydrates=40,
        fats=10,
        fiber=6,
        servings=1,
        is_active=True,
    )
    # Receta propia de Beta
    recipe_b = Recipe(
        id="recipe-beta-01",
        tenant_id=t2.id,
        created_by=nutri_b.id,
        title="Batido Proteico Beta",
        category="Desayuno",
        difficulty="Fácil",
        ingredients="Proteína en polvo, plátano, leche de almendras",
        instructions="Licuar todos los ingredientes por 2 minutos.",
        calories=280,
        protein=25,
        carbohydrates=20,
        fats=5,
        fiber=4,
        servings=1,
        is_active=True,
    )
    db_session.add_all([recipe_a, recipe_b])
    db_session.commit()

    token_a = create_access_token(data={"sub": nutri_a.id, "email": nutri_a.email, "role": nutri_a.role_id, "tenant_id": t1.id})
    token_b = create_access_token(data={"sub": nutri_b.id, "email": nutri_b.email, "role": nutri_b.role_id, "tenant_id": t2.id})

    return {
        "tenant_a": t1,
        "tenant_b": t2,
        "nutri_a": nutri_a,
        "nutri_b": nutri_b,
        "token_a": token_a,
        "token_b": token_b,
        "recipe_a": recipe_a,
        "recipe_b": recipe_b,
    }


def test_recipe_tenant_isolation(multi_tenant_setup, client):
    token_a = multi_tenant_setup["token_a"]
    token_b = multi_tenant_setup["token_b"]

    # Nutri Alpha solo debe ver recetas de Alpha
    res_a = client.get("/api/v1/recipes", headers={"Authorization": f"Bearer {token_a}"})
    assert res_a.status_code == 200
    recipes_a = res_a.json()
    titles_a = [r["title"] for r in recipes_a]
    assert "Ensalada Quinoa Alpha" in titles_a
    assert "Batido Proteico Beta" not in titles_a

    # Nutri Beta solo debe ver recetas de Beta
    res_b = client.get("/api/v1/recipes", headers={"Authorization": f"Bearer {token_b}"})
    assert res_b.status_code == 200
    recipes_b = res_b.json()
    titles_b = [r["title"] for r in recipes_b]
    assert "Batido Proteico Beta" in titles_b
    assert "Ensalada Quinoa Alpha" not in titles_b


def test_backup_tenant_isolation(multi_tenant_setup, client):
    token_a = multi_tenant_setup["token_a"]
    token_b = multi_tenant_setup["token_b"]

    # Exportar backup para Tenant Alpha
    res_exp_a = client.post("/api/v1/backup/export", headers={"Authorization": f"Bearer {token_a}"})
    assert res_exp_a.status_code == 200
    log_a = res_exp_a.json()
    assert log_a["tenant_id"] == "tenant-clinica-alpha"

    # Historial de Alpha solo debe listar respaldos de Alpha
    res_hist_a = client.get("/api/v1/backup/history", headers={"Authorization": f"Bearer {token_a}"})
    assert res_hist_a.status_code == 200
    history_a = res_hist_a.json()
    assert all(h["tenant_id"] == "tenant-clinica-alpha" for h in history_a if h.get("tenant_id"))


def test_notification_broadcast_tenant(multi_tenant_setup, client, db_session):
    token_a = multi_tenant_setup["token_a"]

    # Enviar broadcast a pacientes de Alpha
    payload = {
        "title": "Recordatorio de Dieta Semanal",
        "message": "Recuerda registrar tus progresos de hidratación y recetas.",
        "type": "SEGUIMIENTO_DIETA",
    }
    res = client.post("/api/v1/notifications/broadcast-tenant", json=payload, headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    assert data["sent_count"] >= 1

    # Verificar que el paciente de Alpha recibió la notificación
    notif = db_session.query(Notification).filter(Notification.user_id == "paciente-alpha-01").first()
    assert notif is not None
    assert notif.title == "Recordatorio de Dieta Semanal"
    assert notif.tenant_id == "tenant-clinica-alpha"

    # Verificar que el paciente de Beta NO recibió la notificación de Alpha
    notif_b = db_session.query(Notification).filter(Notification.user_id == "paciente-beta-01").first()
    assert notif_b is None


def test_reports_tenant_isolation(multi_tenant_setup, client):
    token_a = multi_tenant_setup["token_a"]

    # Reporte de pacientes para Tenant Alpha
    query_req = {
        "entity": "patients",
        "columns": ["full_name", "email"],
    }
    res = client.post("/api/v1/reports/query", json=query_req, headers={"Authorization": f"Bearer {token_a}"})
    assert res.status_code == 200
    data = res.json()
    patient_names = [row.get("full_name") for row in data["rows"]]
    assert "Paciente Alpha" in patient_names
    assert "Paciente Beta" not in patient_names
