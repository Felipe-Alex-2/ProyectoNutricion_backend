import pytest
from app.models.user import User
from app.models.tenant import Tenant
from app.models.payment import Payment
from app.models.rbac import Role
from app.core.security import hash_password, create_access_token


@pytest.fixture
def auth_context(db_session):
    admin_role = Role(id="ADMIN_SAAS", name="Admin SaaS", description="Global", platform="Web")
    db_session.add(admin_role)
    db_session.commit()

    tenant = Tenant(id="tenant-test-1", name="Sucursal Matriz Test", code="MATRIZ1", is_active=True)
    db_session.add(tenant)
    db_session.commit()

    admin = User(
        id="admin-test-id",
        email="admin@testvalidations.com",
        hashed_password=hash_password("Password123!"),
        full_name="Admin Validador",
        role_id="ADMIN_SAAS",
        tenant_id=tenant.id,
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    token = create_access_token(data={"sub": admin.id, "email": admin.email})
    return {
        "headers": {"Authorization": f"Bearer {token}"},
        "tenant": tenant,
        "admin": admin,
    }


def test_tenant_validations(client, auth_context):
    headers = auth_context["headers"]

    # 1. Intentar crear tenant con nombre vacio o espacios
    res_empty = client.post(
        "/api/v1/tenants",
        json={"name": "   ", "code": "TESTV"},
        headers=headers,
    )
    assert res_empty.status_code in [400, 422]
    assert "El campo no puede estar" in str(res_empty.json()) or "El nombre de la sucursal es obligatorio" in str(res_empty.json())

    # 2. Crear una sucursal valida
    tenant_name = "Clinica Validacion Test 2026"
    tenant_code = "VALTEST1"
    res_ok = client.post(
        "/api/v1/tenants",
        json={"name": tenant_name, "code": tenant_code},
        headers=headers,
    )
    assert res_ok.status_code == 201

    # 3. Intentar crear duplicado con el mismo nombre
    res_dup = client.post(
        "/api/v1/tenants",
        json={"name": tenant_name, "code": "VALTEST2"},
        headers=headers,
    )
    assert res_dup.status_code == 409
    assert "Ya existe una sucursal con el nombre" in res_dup.json()["detail"]


def test_recipe_validations(client, auth_context):
    headers = auth_context["headers"]

    # 1. Intentar crear receta sin calorias ni proteinas obligatorias
    res_missing = client.post(
        "/api/v1/recipes",
        json={
            "title": "Receta Incompleta",
            "ingredients": "Ingrediente 1",
            "instructions": "Instruccion 1",
        },
        headers=headers,
    )
    assert res_missing.status_code == 422

    # 2. Crear una receta valida
    recipe_title = "Pollo al Limon Test Val 2026"
    res_ok = client.post(
        "/api/v1/recipes",
        json={
            "title": recipe_title,
            "calories": 420.0,
            "protein": 35.0,
            "carbohydrates": 25.0,
            "fats": 12.0,
            "ingredients": "150g pechuga de pollo, 1 limon, sal al gusto",
            "instructions": "1. Marinar el pollo. 2. Cocinar a la plancha por 10 minutos.",
            "category": "Almuerzo",
            "difficulty": "Fácil",
            "servings": 1,
        },
        headers=headers,
    )
    assert res_ok.status_code == 201

    # 3. Intentar crear receta con el mismo nombre (duplicado)
    res_dup = client.post(
        "/api/v1/recipes",
        json={
            "title": recipe_title,
            "calories": 420.0,
            "protein": 35.0,
            "carbohydrates": 25.0,
            "fats": 12.0,
            "ingredients": "150g pechuga de pollo, 1 limon",
            "instructions": "1. Cocinar a la plancha.",
            "category": "Almuerzo",
            "difficulty": "Fácil",
            "servings": 1,
        },
        headers=headers,
    )
    assert res_dup.status_code == 400
    assert "No se permite repetir el mismo nombre" in res_dup.json()["detail"]


def test_payment_pdf_export(client, db_session, auth_context):
    headers = auth_context["headers"]
    tenant = auth_context["tenant"]

    payment = Payment(
        id="pay-test-12345",
        tenant_id=tenant.id,
        customer_name="Juan Perez Test",
        customer_email="juan@test.com",
        concept="Consulta Nutricional Inicial",
        amount=50.0,
        currency="USD",
        status="COMPLETED",
        payment_method="EFECTIVO",
    )
    db_session.add(payment)
    db_session.commit()

    res_pdf = client.get(f"/api/v1/payments/{payment.id}/pdf", headers=headers)
    assert res_pdf.status_code == 200
    assert res_pdf.headers["content-type"] == "application/pdf"
    assert "Detalle_Pago_" in res_pdf.headers["content-disposition"]
    # PDF files start with %PDF
    assert res_pdf.content.startswith(b"%PDF")

