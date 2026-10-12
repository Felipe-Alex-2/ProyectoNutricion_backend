from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from app.core.security import create_access_token
from app.models.user import User
from app.models.rbac import Role
from app.models.subscription import Subscription
from app.models.subscription_receipt import SubscriptionReceipt
from app.services.paypal_service import PayPalService
from app.services.subscription_service import SubscriptionService


def auth(user_id):
    return {'Authorization': f'Bearer {create_access_token(subject=user_id)}'}


@pytest.fixture
def pending(db_session):
    db_session.add(Role(id='CLIENTE', name='Patient', description='Patient', platform='Mobile'))
    db_session.add_all([User(id='buyer', email='buyer@example.com', full_name='María <Pérez>', hashed_password='unused', role_id='CLIENTE'),
                        User(id='stranger', email='other@example.com', full_name='Other', hashed_password='unused', role_id='CLIENTE')])
    sub = Subscription(id='7ad7bad4-9f11-4ad4-829b-5c40b3f1a912', user_id='buyer', plan_name='CLIENTE_PREMIUM', amount=5, currency='USD', status='PENDING', paypal_order_id='ORDER-123')
    db_session.add(sub)
    db_session.commit()
    return sub


def completed(amount='5.00'):
    return {'id': 'ORDER-123', 'status': 'COMPLETED', 'purchase_units': [{'payments': {'captures': [
        {'id': 'CAPTURE-123', 'status': 'COMPLETED', 'amount': {'value': amount, 'currency_code': 'USD'}}]}}]}


@pytest.mark.parametrize('provider_status', ['APPROVED', 'COMPLETED'])
def test_confirmed_checkout_issues_one_durable_receipt(client, db_session, pending, monkeypatch, provider_status):
    queries = []
    def get_order(order):
        queries.append(order)
        return {'status': 'APPROVED'} if provider_status == 'APPROVED' else completed()
    monkeypatch.setattr(PayPalService, 'get_order', get_order)
    monkeypatch.setattr(PayPalService, 'capture_order', lambda _: {'status': 'COMPLETED', 'capture_id': 'CAPTURE-123', 'raw': completed()})
    for _ in range(2):
        response = client.post('/api/v1/subscriptions/verify-order', headers=auth('buyer'), json={'order_id': 'ORDER-123'})
        assert response.status_code == 200, response.text
        assert response.json()['paid']
    assert queries == ['ORDER-123']
    assert db_session.query(SubscriptionReceipt).count() == 1
    receipt = db_session.get(SubscriptionReceipt, pending.id)
    assert receipt.amount == Decimal('5.00')
    assert receipt.paypal_capture_id == 'CAPTURE-123'
    # The paid document remains after cancellation and edits to the user profile.
    pending.status = 'CANCELLED'
    db_session.get(User, 'buyer').full_name = 'Changed name'
    db_session.commit()
    listing = client.get('/api/v1/subscriptions/receipts', headers=auth('buyer'))
    assert listing.status_code == 200
    assert listing.json()[0]['buyer_name'] == 'María <Pérez>'
    assert listing.json()[0]['paid_at'].endswith('+00:00')
    pdf = client.get(f'/api/v1/subscriptions/receipts/{pending.id}/pdf', headers=auth('buyer'))
    assert pdf.status_code == 200
    assert pdf.headers['content-type'] == 'application/pdf'
    assert pdf.content.startswith(b'%PDF-')
    assert pdf.headers['cache-control'] == 'private, no-store'


def test_capture_endpoint_also_issues_receipt(client, pending, db_session, monkeypatch):
    monkeypatch.setattr(PayPalService, 'capture_order', lambda _: {'status': 'COMPLETED', 'capture_id': 'CAPTURE-123', 'raw': completed()})
    response = client.post('/api/v1/subscriptions/capture', headers=auth('buyer'), json={'order_id': 'ORDER-123'})
    assert response.status_code == 200, response.text
    assert db_session.get(SubscriptionReceipt, pending.id) is not None


def test_unpaid_or_mismatched_payments_never_issue_receipt(client, pending, db_session, monkeypatch):
    monkeypatch.setattr(PayPalService, 'get_order', lambda _: {'status': 'CREATED'})
    response = client.post('/api/v1/subscriptions/verify-order', headers=auth('buyer'), json={'order_id': 'ORDER-123'})
    assert response.status_code == 200
    assert not response.json()['paid']
    assert db_session.query(SubscriptionReceipt).count() == 0
    monkeypatch.setattr(PayPalService, 'get_order', lambda _: completed('0.01'))
    assert client.post('/api/v1/subscriptions/verify-order', headers=auth('buyer'), json={'order_id': 'ORDER-123'}).status_code == 400
    assert db_session.query(SubscriptionReceipt).count() == 0
    assert pending.status == 'PENDING'


def test_receipt_requires_owner_and_cannot_be_downloaded_by_url_token(client, pending, db_session, monkeypatch):
    monkeypatch.setattr(PayPalService, 'get_order', lambda _: completed())
    SubscriptionService.verify_and_capture_order(db_session, 'ORDER-123', 'buyer')
    path = f'/api/v1/subscriptions/receipts/{pending.id}/pdf'
    assert client.get(path).status_code == 401
    assert client.get(path + '?token=' + create_access_token(subject='buyer')).status_code == 401
    assert client.get(path, headers=auth('stranger')).status_code == 404
    assert client.get('/api/v1/subscriptions/receipts', headers=auth('stranger')).json() == []


def test_receipt_history_pagination_is_bounded(client, pending):
    assert client.get('/api/v1/subscriptions/receipts?limit=101', headers=auth('buyer')).status_code == 422
    assert client.get('/api/v1/subscriptions/receipts?offset=-1', headers=auth('buyer')).status_code == 422
