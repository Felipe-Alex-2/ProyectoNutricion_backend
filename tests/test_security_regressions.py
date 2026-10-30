import json
from pathlib import Path
import pytest
from sqlalchemy import event
from app.models.user import User
from app.models.tenant import Tenant
from app.models.rbac import Role, Permission
from app.models.patient_link import PatientNutritionistLink
from app.models.payment import Payment
from app.models.subscription import Subscription
from app.core.security import create_access_token
from app.services.backup_service import BackupService
from app.services.user_service import UserService


@pytest.fixture
def accounts(db_session):
    for role in ["SUPERADMIN", "ADMIN_ORGANIZATION", "NUTRICIONISTA", "CLIENTE"]:
        db_session.add(Role(id=role, name=role, description=role, platform="Web"))
    db_session.add_all([Tenant(id="a", name="Clinic A", code="A"), Tenant(id="b", name="Clinic B", code="B"), Permission(id="roles:manage", name="Roles", description="Roles", module="SaaS")])
    db_session.commit()
    users = {}
    for identity, role, tenant in [("patient", "CLIENTE", "a"), ("other", "CLIENTE", "b"), ("nutri", "NUTRICIONISTA", "a"), ("org", "ADMIN_ORGANIZATION", "a"), ("global", "SUPERADMIN", None)]:
        user = User(id=identity, full_name=identity, email=f"{identity}@example.com", hashed_password="unused", role_id=role, tenant_id=tenant, is_active=True)
        db_session.add(user)
        users[identity] = user
    db_session.commit()
    return users


def headers(identity):
    return {"Authorization": f"Bearer {create_access_token(subject=identity)}"}


@pytest.mark.parametrize("field,value", [("role_id", "SUPERADMIN"), ("tenant_id", "b"), ("is_active", False)])
def test_profile_cannot_modify_administrative_fields(client, accounts, field, value):
    response = client.put("/api/v1/users/me", headers=headers("patient"), json={field: value})
    assert response.status_code == 422
    assert accounts["patient"].role_id == "CLIENTE"
    assert accounts["patient"].tenant_id == "a"


@pytest.mark.parametrize("method,path,body", [
    ("put", "/organization-users/other", {"role_id": "SUPERADMIN"}),
    ("delete", "/organization-users/other", None),
    ("patch", "/organization-users/other/toggle-status", None),
    ("put", "/roles/CLIENTE/permissions", {"permission_ids": ["roles:manage"]}),
    ("post", "/tenants", {"name": "Attack Clinic", "code": "ATTACK"}),
])
def test_patient_cannot_administer_resources(client, accounts, method, path, body):
    kwargs = {"headers": headers("patient")}
    if body is not None:
        kwargs["json"] = body
    assert getattr(client, method)("/api/v1" + path, **kwargs).status_code == 403
    assert accounts["other"].role_id == "CLIENTE"


def test_public_web_registration_is_patient(client):
    response = client.post("/api/v1/auth/register", json={"email": "public@example.com", "full_name": "Public User", "password": "Password123!", "client_platform": "web"})
    assert response.status_code == 201
    assert response.json()["role_id"] == "CLIENTE"


@pytest.mark.parametrize("actor", ["org", "nutri"])
def test_other_clinic_records_and_profile_are_denied(client, accounts, actor):
    assert client.get("/api/v1/clinical/patients/other/records", headers=headers(actor)).status_code == 403
    assert client.get("/api/v1/plans/patient/other", headers=headers(actor)).status_code == 403
    assert client.put("/api/v1/users/patients/other", headers=headers(actor), json={"full_name": "Changed"}).status_code == 403


def test_nutritionist_needs_active_patient_link(client, db_session, accounts):
    assert client.get("/api/v1/clinical/patients/patient/records", headers=headers("nutri")).status_code == 403
    db_session.add(PatientNutritionistLink(patient_id="patient", nutritionist_id="nutri", tenant_id="a", pairing_code="SAFE", status="LINKED"))
    db_session.commit()
    assert client.get("/api/v1/clinical/patients/patient/records", headers=headers("nutri")).status_code == 200


def test_sandbox_activation_is_retired(client, accounts):
    assert client.post("/api/v1/subscriptions/validate-sandbox", headers=headers("patient")).status_code == 410


def test_receipt_requires_auth_and_clinic_access(client, db_session, accounts):
    db_session.add(Payment(id="payment-b", tenant_id="b", customer_name="Other Patient", concept="Consultation", amount=50, currency="USD", status="PENDING"))
    db_session.commit()
    assert client.get("/api/v1/payments/payment-b/pdf").status_code == 401
    assert client.get("/api/v1/payments/payment-b/pdf", headers=headers("org")).status_code == 403
    assert client.post("/api/v1/payments/payment-b/cancel", headers=headers("org")).status_code == 403


def test_other_buyers_order_is_not_verified(client, db_session, accounts, monkeypatch):
    from app.services.paypal_service import PayPalService
    monkeypatch.setattr(PayPalService, "get_order", lambda _: pytest.fail("Ownership must be checked before PayPal"))
    db_session.add(Subscription(user_id="other", plan_name="CLIENTE_PREMIUM", paypal_order_id="someone-elses-order", status="PENDING", amount=5, currency="USD"))
    db_session.commit()
    assert client.post("/api/v1/subscriptions/verify-order", headers=headers("patient"), json={"order_id": "someone-elses-order"}).status_code == 404


def test_tokens_in_query_string_are_rejected(client, accounts):
    assert client.get("/api/v1/users/me", params={"token": create_access_token(subject="patient")}).status_code == 401


def login_user(client):
    body = {"email": "session@example.com", "full_name": "Session User", "password": "Password123!"}
    client.post("/api/v1/auth/register", json=body)
    return client.post("/api/v1/auth/login", json={"email": body["email"], "password": body["password"]}).json()


def test_refresh_rotation_and_logout_revoke_refresh(client):
    tokens = login_user(client)
    first = tokens["refresh_token"]
    result = client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert result.status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": first}).status_code == 401
    renewed = result.json()
    assert client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {renewed['access_token']}"}, json={"refresh_token": renewed["refresh_token"]}).status_code == 200
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": renewed["refresh_token"]}).status_code == 401


def test_password_change_invalidates_existing_sessions(client):
    tokens = login_user(client)
    authorization = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.put("/api/v1/users/me", headers=authorization, json={"password": "NewPassword123!"}).status_code == 200
    assert client.get("/api/v1/users/me", headers=authorization).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 401


def test_encrypted_backup_and_global_download_denial(client, db_session, accounts):
    result = BackupService.create_backup(db_session, tenant_id="b")
    raw = Path(result["filepath"]).read_text()
    assert '"ciphertext"' in raw and "hashed_password" not in raw
    envelope = json.loads(raw)
    snapshot = json.loads(BackupService._cipher().decrypt(envelope["ciphertext"].encode()))
    assert set(snapshot["tables"]) == {"payments", "recipes", "recipe_assignments", "nutritional_plans", "appointments", "activity_logs", "generated_reports"}
    assert client.get(f"/api/v1/backup/download/{result['filename']}", headers=headers("org")).status_code == 403
    assert client.post("/api/v1/backup/preview", headers=headers("org"), files={"file": ("backup.json", raw, "application/json")}).status_code == 400
    envelope["ciphertext"] = "altered"
    from app.services.backup_recovery_service import BackupRecoveryService
    with pytest.raises(ValueError): BackupRecoveryService.parse(envelope,"b")


def test_patient_list_uses_bounded_query_count(db_session, accounts):
    for number in range(15):
        user = User(id=f"p{number}", email=f"p{number}@example.com", full_name=f"Patient {number}", hashed_password="unused", role_id="CLIENTE", tenant_id="a")
        db_session.add(user)
        db_session.add(PatientNutritionistLink(patient_id=user.id, nutritionist_id="nutri", tenant_id="a", pairing_code=f"CODE{number}", status="LINKED"))
    db_session.commit()
    statements = []
    def count(*args): statements.append(args[2])
    event.listen(db_session.bind, "before_cursor_execute", count)
    try:
        patients = UserService.list_patients(db_session, tenant_id="a", nutritionist_id="nutri", limit=10)
    finally:
        event.remove(db_session.bind, "before_cursor_execute", count)
    assert len(patients) == 10
    assert len(statements) == 2


def test_appointment_retry_is_idempotent_and_other_patients_cannot_cancel(client, accounts, db_session):
    from app.models.appointment import Appointment
    body = {"nutritionist_id": "nutri", "scheduled_at": "2030-01-01T10:00:00Z", "reason": "Checkup"}
    request_headers = {**headers("patient"), "Idempotency-Key": "offline-123"}
    first = client.post("/api/v1/appointments", headers=request_headers, json=body)
    assert first.status_code == 200, first.text
    retry = client.post("/api/v1/appointments", headers=request_headers, json=body)
    assert retry.status_code == 200
    assert retry.json()["id"] == first.json()["id"]
    assert db_session.query(Appointment).count() == 1
    changed = client.post("/api/v1/appointments", headers=request_headers, json={**body, "reason": "Other"})
    assert changed.status_code == 409
    cancellation = client.post(f"/api/v1/appointments/{first.json()['id']}/cancel", headers=headers("other"))
    assert cancellation.status_code == 403
    assert client.post(f"/api/v1/appointments/{first.json()['id']}/cancel", headers=headers("patient")).status_code == 200


def test_appointment_tenant_and_specialist_are_enforced(client, accounts):
    body = {"nutritionist_id": "nutri", "scheduled_at": "2030-01-01T10:00:00Z"}
    assert client.post("/api/v1/appointments", headers=headers("other"), json=body).status_code == 403
    assert client.post("/api/v1/appointments", headers=headers("patient"), json={**body, "nutritionist_id": "org"}).status_code == 404
    assert client.get("/api/v1/appointments/nutritionists?tenant_id=b", headers=headers("patient")).status_code == 403


@pytest.mark.parametrize("amount,currency,status", [("0.01", "USD", "COMPLETED"), ("5.00", "EUR", "COMPLETED"), ("5.00", "USD", "PENDING")])
def test_paypal_capture_requires_matching_completed_amount(amount, currency, status):
    from app.services.paypal_service import PayPalService
    order = {"status": "COMPLETED", "purchase_units": [{"payments": {"captures": [{"id": "capture", "status": status, "amount": {"value": amount, "currency_code": currency}}]}}]}
    with pytest.raises(ValueError):
        PayPalService.validate_completed_payment(order, 5, "USD")


def test_paypal_completed_capture_accepts_exact_amount():
    from app.services.paypal_service import PayPalService
    order = {"status": "COMPLETED", "purchase_units": [{"payments": {"captures": [{"id": "capture", "status": "COMPLETED", "amount": {"value": "5.00", "currency_code": "USD"}}]}}]}
    assert PayPalService.validate_completed_payment(order, 5, "USD")["id"] == "capture"


def test_backup_never_restores_accounts_or_overwrites_existing(db_session, accounts):
    from app.services.backup_recovery_service import BackupRecoveryService
    from app.core.security import hash_password
    accounts["org"].hashed_password = hash_password("Password123!")
    db_session.commit()
    backup = BackupService.create_backup(db_session, tenant_id="a")
    content = Path(backup["filepath"]).read_bytes()
    accounts["patient"].full_name = "Changed after backup"
    db_session.commit()
    preview = BackupRecoveryService.preview(db_session, content, "a", accounts["org"])
    result = BackupRecoveryService.restore(db_session, content,"a",accounts["org"],preview["review_token"],"Password123!")
    assert result["success"]
    assert accounts["patient"].full_name == "Changed after backup"
    assert accounts["patient"].session_version == 0
