from app.models.payment import Payment
from app.models.recipe import Recipe
from app.models.ai_nutrition import FoodRecord
from app.services.gemini_service import GeminiService
from tests.test_security_regressions import accounts, headers


def test_cash_lost_response_retries_once_and_rejects_changed_amount(client, db_session, accounts):
    auth = {**headers('org'), 'Idempotency-Key': 'cash-operation-1'}
    payload = dict(tenant_id='a', customer_name='Cliente Ejemplo', concept='Consulta',
                   amount=5, currency='USD', payment_method='EFECTIVO')
    first = client.post('/api/v1/payments/create', headers=auth, json=payload)
    retry = client.post('/api/v1/payments/create', headers=auth, json=payload)
    assert first.status_code == retry.status_code == 200, retry.text
    assert first.json()['payment_id'] == retry.json()['payment_id']
    assert db_session.query(Payment).count() == 1
    assert client.post('/api/v1/payments/create', headers=auth, json={**payload, 'amount': 10}).status_code == 409
    assert client.post('/api/v1/payments/create', headers={**headers('other'), 'Idempotency-Key': 'cash-operation-1'}, json=payload).status_code == 403
    assert client.post('/api/v1/payments/create', headers=auth, json={**payload, 'payment_method': 'PAYPAL'}).status_code == 422


def test_recipe_replay_survives_duplicate_title_check(client, db_session, accounts):
    auth = {**headers('org'), 'Idempotency-Key': 'recipe-operation-1'}
    payload = dict(title='Arroz con verduras', calories=250, protein=8, carbohydrates=40,
                   fats=5, ingredients='Arroz y verduras', instructions='Cocinar y servir.', assigned_patient_ids=['patient'])
    first = client.post('/api/v1/recipes', headers=auth, json=payload)
    retry = client.post('/api/v1/recipes', headers=auth, json=payload)
    assert first.status_code == retry.status_code == 201, retry.text
    assert first.json()['id'] == retry.json()['id']
    assert retry.json()['assigned_patient_ids'] == ['patient']
    assert db_session.query(Recipe).count() == 1
    assert client.post('/api/v1/recipes', headers=auth, json={**payload, 'calories': 900}).status_code == 409
    assert client.post('/api/v1/recipes', headers={**headers('org'), 'Idempotency-Key': 'another-key'}, json=payload).status_code == 400


def test_photo_lost_response_does_not_analyze_or_register_twice(client, db_session, accounts, monkeypatch):
    calls = []
    def analyze(**kwargs):
        calls.append(kwargs)
        return {'alimentos': [{'nombre': 'Manzana', 'calorias': 95}],
                'total': {'calorias': 95}, 'confianza': 'media'}
    monkeypatch.setattr(GeminiService, 'analyze_image', analyze)
    auth = {**headers('patient'), 'Idempotency-Key': 'photo-operation-1'}
    image = {'file': ('food.jpg', b'\xff\xd8\xffabc', 'image/jpeg')}
    first = client.post('/api/v1/food/analyze', headers=auth, files=image)
    retry = client.post('/api/v1/food/analyze', headers=auth, files=image)
    assert first.status_code == retry.status_code == 200, retry.text
    assert first.json()['record_id'] == retry.json()['record_id']
    assert retry.json()['total']['calorias'] == 95
    assert len(calls) == db_session.query(FoodRecord).count() == 1
    assert client.post('/api/v1/food/analyze', headers=auth,
        files={'file': ('changed.jpg', b'\xff\xd8\xffother', 'image/jpeg')}).status_code == 409
    assert len(calls) == 1
