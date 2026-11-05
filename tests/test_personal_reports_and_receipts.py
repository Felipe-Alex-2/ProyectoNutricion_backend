from datetime import datetime, timedelta
from decimal import Decimal
import json
import pytest
from app.core.security import create_access_token
from app.models.rbac import Role
from app.models.user import User
from app.models.tenant import Tenant
from app.models.payment import Payment
from app.models.ai_nutrition import FoodRecord
from app.models.subscription import Subscription
from app.models.subscription_receipt import SubscriptionReceipt


def auth(who): return {'Authorization': 'Bearer ' + create_access_token(subject=who)}


@pytest.fixture
def personal(db_session):
    db_session.add(Role(id='CLIENTE', name='Cliente', description='Cliente', platform='Mobile'))
    db_session.add(Tenant(id='clinic', name='Clínica', code='CL'))
    db_session.flush()
    for who in ['owner','other']:
        db_session.add(User(id=who, full_name=who, email=who+'@example.com', hashed_password='unused', role_id='CLIENTE', tenant_id='clinic', is_active=True))
    db_session.flush()
    now=datetime(2026,11,3,12)
    for who in ['owner','other']:
        db_session.add(FoodRecord(id='food-'+who,patient_id=who,result_json=json.dumps({'description':'Almuerzo '+who}),
            confidence='manual',estimated_calories=350,estimated_protein=20,estimated_carbs=30,estimated_fats=10,created_at=now))
        for purpose in ['CONSULTATION','WALLET_TOPUP']:
            db_session.add(Payment(id=purpose+'-'+who,patient_id=who,tenant_id='clinic',purpose=purpose,
                customer_name=who,customer_email=who+'@example.com',concept=purpose+' '+who,
                amount=5,currency='USD',status='COMPLETED',payment_method='WALLET' if purpose=='CONSULTATION' else 'PAYPAL',paid_at=now))
        db_session.add(Subscription(id='sub-'+who,user_id=who,plan_name='CLIENTE_PREMIUM',amount=5,currency='USD',status='CANCELLED'))
        db_session.flush()
        db_session.add(SubscriptionReceipt(id='sub-'+who,user_id=who,buyer_name=who,buyer_email=who+'@example.com',
            plan_name='CLIENTE_PREMIUM',amount=Decimal('5'),currency='USD',paypal_order_id='order-'+who,
            paypal_capture_id='capture-'+who,is_sandbox=True,paid_at=now,expires_at=now+timedelta(days=30)))
    db_session.add(Payment(id='pending',patient_id='owner',tenant_id='clinic',purpose='WALLET_TOPUP',customer_name='owner',
        concept='Sin pagar',amount=5,status='PENDING',payment_method='PAYPAL'))
    db_session.commit()


def test_free_account_reports_are_private_and_exportable(client, personal):
    # There is no ACTIVE subscription; the tools are available to free accounts.
    for entity,expected in [('food',1),('payments',2),('subscriptions',1),('appointments',0)]:
        response=client.get('/api/v1/reports/mine?entity='+entity,headers=auth('owner'))
        assert response.status_code==200,response.text
        assert response.json()['total_rows']==expected
        assert 'other' not in json.dumps(response.json())
    assert client.get('/api/v1/reports/entities',headers=auth('owner')).status_code==200
    assert client.get('/api/v1/reports/mine?entity=patients',headers=auth('owner')).status_code==422
    assert client.get('/api/v1/reports/mine?start_date=invalid',headers=auth('owner')).status_code==422
    assert client.get('/api/v1/reports/mine?start_date=2026-11-04&end_date=2026-11-03',headers=auth('owner')).status_code==422
    assert client.get('/api/v1/reports/mine?entity=food&start_date=2026-11-04',headers=auth('owner')).json()['total_rows']==0
    assert client.get('/api/v1/reports/mine?entity=food&end_date=2026-11-03',headers=auth('owner')).json()['total_rows']==1
    for format,signature in [('pdf',b'%PDF'),('excel',b'PK')]:
        response=client.get('/api/v1/reports/mine/export?entity=food&file_format='+format,headers=auth('owner'))
        assert response.status_code==200,response.text[:300]
        assert response.content.startswith(signature)


def test_each_completed_mobile_payment_has_its_own_detailed_receipt(client, personal):
    response=client.get('/api/v1/my-receipts',headers=auth('owner'))
    assert response.status_code==200,response.text
    rows=response.json()
    assert len(rows)==3
    assert {r['kind'] for r in rows}=={'CONSULTATION','WALLET_TOPUP','SUBSCRIPTION'}
    assert all(r['buyer_name']=='owner' and r['amount']==5 and r['paid_at'] and r['reference'] for r in rows)
    for row in rows:
        assert client.get('/api/v1'+row['pdf_path'],headers=auth('owner')).content.startswith(b'%PDF')
        assert client.get('/api/v1'+row['pdf_path'],headers=auth('other')).status_code in {403,404}
    paged=client.get('/api/v1/my-receipts?limit=1&offset=1',headers=auth('owner')).json()
    assert paged==rows[1:2]
    assert client.get('/api/v1/my-receipts?limit=101',headers=auth('owner')).status_code==422


def test_free_food_history_remains_self_scoped(client, personal):
    history=client.get('/api/v1/food/history',headers=auth('owner'))
    assert history.status_code==200 and len(history.json())==1
    assert history.json()[0]['patient_id']=='owner'
    assert client.get('/api/v1/food/history?patient_id=other',headers=auth('owner')).status_code==403
