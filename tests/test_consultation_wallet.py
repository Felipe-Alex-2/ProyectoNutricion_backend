from datetime import datetime, timedelta, timezone
from decimal import Decimal
import pytest
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.wallet import WalletMovement
from app.models.user import User
from app.models.tenant import Tenant
from app.models.company import Branch
from app.models.rbac import Role
from app.core.security import create_access_token
from app.services.paypal_service import PayPalService


def auth(who):
    return {'Authorization': 'Bearer ' + create_access_token(subject=who)}


@pytest.fixture
def setup(db_session):
    db = db_session
    for role in ['SUPERADMIN', 'ADMIN_ORGANIZATION', 'NUTRICIONISTA', 'CLIENTE']:
        db.add(Role(id=role, name=role, description=role, platform='Web'))
    db.add(Tenant(id='a', name='Empresa A', code='AA'))
    db.flush()
    db.add(Branch(id='a1', tenant_id='a', name='Sucursal', code='PRI'))
    db.flush()
    for identity, role in [('patient','CLIENTE'), ('other','CLIENTE'), ('doctor','NUTRICIONISTA'), ('admin','ADMIN_ORGANIZATION')]:
        db.add(User(id=identity, email=identity+'@example.com', full_name=identity, hashed_password='unused', role_id=role, tenant_id='a', branch_id='a1', is_active=True))
    db.flush()
    db.add(Appointment(id='appointment', patient_id='patient', nutritionist_id='doctor', tenant_id='a', branch_id='a1', scheduled_at=datetime.now(timezone.utc)+timedelta(days=1), status='PENDING'))
    db.commit()


def accept(client):
    r=client.post('/api/v1/appointments/appointment/confirm', headers=auth('admin'))
    assert r.status_code == 200, r.text
    assert r.json()['status'] == 'ACCEPTED'


def test_accept_creates_pending_charge_and_cash_confirms_once(client, db_session, setup):
    assert client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'WALLET'}).status_code == 409
    accept(client)
    charge=db_session.query(Payment).one()
    assert (charge.amount,charge.patient_id,charge.customer_email,charge.branch_id,charge.status)==(5,'patient','patient@example.com','a1','PENDING')
    assert client.post('/api/v1/appointments/appointment/pay',headers=auth('other'),json={'method':'PAYPAL'}).status_code==403
    assert client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'EFECTIVO'}).status_code==403
    for _ in range(2):
        paid=client.post('/api/v1/appointments/appointment/pay',headers=auth('admin'),json={'method':'EFECTIVO'})
        assert paid.status_code==200,paid.text
    assert db_session.query(Payment).count()==1
    assert db_session.get(Appointment,'appointment').status=='CONFIRMED'
    assert client.get('/api/v1/my-payments',headers=auth('other')).json()==[]
    assert client.get(f'/api/v1/payments/{charge.id}/pdf',headers=auth('other')).status_code==403
    assert client.get(f'/api/v1/payments/{charge.id}/pdf',headers=auth('patient')).status_code==403
    assert client.get(f'/api/v1/payments/{charge.id}/pdf',headers=auth('admin')).status_code==200
    assert client.get('/api/v1/my-payments',headers=auth('patient')).json()==[]


def completed(amount):
    return {'status':'COMPLETED','purchase_units':[{'payments':{'captures':[{'id':'CAPTURE','status':'COMPLETED','amount':{'value':str(amount),'currency_code':'USD'}}]}}]}


def test_verified_topup_wallet_payment_and_duplicate_capture(client, db_session, setup, monkeypatch):
    monkeypatch.setattr(PayPalService,'create_order',staticmethod(lambda **kw: {'order_id':'ORDER','approval_url':'https://www.sandbox.paypal.com/checkoutnow?token=ORDER'}))
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: {'status':'APPROVED'}))
    monkeypatch.setattr(PayPalService,'capture_order',staticmethod(lambda order: {'raw':completed(5)}))
    headers={**auth('patient'),'Idempotency-Key':'topup-test-01'}
    assert client.post('/api/v1/wallet/topups',headers=headers,json={'amount':7}).status_code==422
    topup=client.post('/api/v1/wallet/topups',headers=headers,json={'amount':5})
    assert topup.status_code==200,topup.text
    assert client.get('/api/v1/wallet',headers=auth('patient')).json()['balance']==0
    for _ in range(2):
        response=client.post('/api/v1/payments/capture',headers=auth('patient'),json={'paypal_order_id':'ORDER'})
        assert response.status_code==200,response.text
    assert client.get('/api/v1/wallet',headers=auth('patient')).json()['balance']==5
    assert db_session.query(WalletMovement).count()==1
    accept(client)
    for _ in range(2):
        paid=client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'WALLET'})
        assert paid.status_code==200,paid.text
    assert client.get('/api/v1/wallet',headers=auth('patient')).json()['balance']==0
    assert db_session.query(WalletMovement).count()==2
    assert db_session.get(Appointment,'appointment').status=='CONFIRMED'
    stats=client.get('/api/v1/payments/stats',headers=auth('admin')).json()
    assert stats['total_collected']==0
    assert stats['total_count']==0
    assert client.get('/api/v1/payments',headers=auth('admin')).json()==[]
    report=client.post('/api/v1/reports/query',headers=auth('admin'),json={'entity':'payments','aggregate':True,'metric':'sum','value_field':'amount','group_by':'branch','status':'COMPLETED'})
    assert report.status_code==200,report.text
    assert report.json()['rows']==[]


def test_insufficient_wallet_unapproved_or_wrong_paypal_amount_never_confirms(client, db_session, setup, monkeypatch):
    accept(client)
    assert client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'WALLET'}).status_code==400
    monkeypatch.setattr(PayPalService,'create_order',staticmethod(lambda **kw: {'order_id':'CONSULT','approval_url':'https://www.sandbox.paypal.com/checkoutnow?token=CONSULT'}))
    r=client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'PAYPAL'})
    assert r.status_code==200,r.text
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: {'status':'CREATED'}))
    capture=lambda: client.post('/api/v1/payments/capture',headers=auth('patient'),json={'paypal_order_id':'CONSULT'})
    assert capture().status_code==409
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: completed(1)))
    assert capture().status_code==502
    assert db_session.get(Appointment,'appointment').status=='ACCEPTED'
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: completed(5)))
    assert capture().status_code==200
    assert capture().status_code==200
    assert db_session.get(Appointment,'appointment').status=='CONFIRMED'


def test_patient_selects_in_person_without_marking_paid_and_staff_sees_choice(client, db_session, setup):
    path='/api/v1/appointments/appointment/pay'
    assert client.post(path,headers=auth('patient'),json={'method':'PRESENCIAL'}).status_code==409
    accept(client)
    assert client.post(path,headers=auth('other'),json={'method':'PRESENCIAL'}).status_code==403
    selected=client.post(path,headers=auth('patient'),json={'method':'PRESENCIAL'})
    assert selected.status_code==200,selected.text
    assert selected.json()['status']=='PENDING'
    from app.models.notification import Notification
    assert db_session.query(Notification).filter_by(title='Pago presencial pendiente').count()==2
    assert client.post(path,headers=auth('patient'),json={'method':'PRESENCIAL'}).status_code==200
    assert db_session.query(Notification).filter_by(title='Pago presencial pendiente').count()==2
    row=client.get('/api/v1/appointments',headers=auth('admin')).json()[0]
    assert row['payment_preference']=='PRESENCIAL'
    assert row['payment_status']=='UNPAID'
    assert row['status']=='ACCEPTED'
    assert db_session.query(WalletMovement).count()==0
    assert client.post(path,headers=auth('admin'),json={'method':'EFECTIVO'}).status_code==200
    row=client.get('/api/v1/appointments',headers=auth('patient')).json()[0]
    assert row['payment_status']=='PAID'
    assert row['payment_preference']=='PRESENCIAL'
    assert row['payment_method']=='EFECTIVO'
    assert row['status']=='CONFIRMED'
    # Completed charges cannot be reset to an unpaid preference by replaying a request.
    assert client.post(path,headers=auth('patient'),json={'method':'ONLINE'}).json()['status']=='COMPLETED'
    assert db_session.query(Payment).one().payment_method=='EFECTIVO'


def test_online_opens_paypal_and_only_verified_capture_marks_paid(client, db_session, setup, monkeypatch):
    row=client.get('/api/v1/appointments',headers=auth('admin')).json()[0]
    assert row['payment_status']=='UNRECORDED'
    accept(client)
    orders=[]
    def create(**kwargs):
        orders.append(kwargs)
        return {'order_id':'ONLINE','approval_url':'https://www.sandbox.paypal.com/checkoutnow?token=ONLINE'}
    monkeypatch.setattr(PayPalService,'create_order',staticmethod(create))
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: {'status':'CREATED','links':[{'rel':'payer-action','href':'https://www.sandbox.paypal.com/checkoutnow?token=ONLINE'}]}))
    for _ in range(2):
        response=client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'ONLINE','mobile':True})
        assert response.status_code==200,response.text
        assert response.json()['paypal_order_id']=='ONLINE'
        assert 'sandbox.paypal.com' in response.json()['approval_url']
    assert len(orders)==1
    assert orders[0]['amount']==5
    row=client.get('/api/v1/appointments',headers=auth('admin')).json()[0]
    assert row['payment_preference']=='ONLINE'
    assert row['payment_status']=='UNPAID'
    # A live order cannot also be charged in cash or from the wallet.
    assert client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'WALLET'}).status_code==409
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: completed(5)))
    assert client.post('/api/v1/payments/capture',headers=auth('patient'),json={'paypal_order_id':'ONLINE'}).status_code==200
    row=client.get('/api/v1/appointments',headers=auth('admin')).json()[0]
    assert row['payment_status']=='PAID'
    assert row['payment_method']=='PAYPAL'


def test_postgres_payment_locks_only_the_payment_table(client, db_session, setup, monkeypatch):
    # SQLite ignores FOR UPDATE; compile the actual endpoint queries for Postgres
    # to catch the nullable eager-join failure that SQLite endpoint tests miss.
    from sqlalchemy import event
    from sqlalchemy.dialects import postgresql
    statements=[]
    def inspect_lock(state):
        statement=state.statement
        if getattr(statement, '_for_update_arg', None) is not None:
            statements.append(str(statement.compile(dialect=postgresql.dialect())))
    event.listen(db_session, 'do_orm_execute', inspect_lock)
    try:
        accept(client)
        monkeypatch.setattr(PayPalService,'create_order',staticmethod(lambda **kw: {'order_id':'LOCK','approval_url':'https://www.sandbox.paypal.com/checkoutnow?token=LOCK'}))
        monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: {'status':'CREATED','links':[]}))
        assert client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'ONLINE'}).status_code==200
        payment=db_session.query(Payment).one()
        assert client.post(f'/api/v1/my-payments/{payment.id}/checkout',headers=auth('patient')).status_code==200
        monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: completed(5)))
        assert client.post('/api/v1/payments/capture',headers=auth('patient'),json={'paypal_order_id':'LOCK'}).status_code==200
        assert client.post('/api/v1/wallet/topups',headers={**auth('patient'),'Idempotency-Key':'lock-topup-test'},json={'amount':5}).status_code==200
    finally:
        event.remove(db_session,'do_orm_execute',inspect_lock)
    payment_locks=[sql for sql in statements if 'FROM payments' in sql]
    assert len(payment_locks)>=4
    assert all('FOR UPDATE OF payments' in sql for sql in payment_locks)


def test_fixed_mobile_checkouts_are_separate_from_variable_web_pos(client, db_session, setup, monkeypatch):
    calls=[]
    def create(**kwargs):
        calls.append(kwargs)
        return {'order_id':f'ORDER-{len(calls)}','approval_url':f'https://www.sandbox.paypal.com/checkoutnow?token=ORDER-{len(calls)}'}
    monkeypatch.setattr(PayPalService,'create_order',staticmethod(create))
    accept(client)
    assert client.get('/api/v1/payments',headers=auth('admin')).json()==[]
    online=client.post('/api/v1/appointments/appointment/pay',headers=auth('patient'),json={'method':'ONLINE','mobile':True})
    assert online.status_code==200,online.text
    for amount in [10,20,50]:
        assert client.post('/api/v1/wallet/topups',headers={**auth('patient'),'Idempotency-Key':'fixed-price-test'},json={'amount':amount}).status_code==422
    topup=client.post('/api/v1/wallet/topups',headers={**auth('patient'),'Idempotency-Key':'fixed-price-test'},json={'amount':5})
    assert topup.status_code==200,topup.text
    sub=client.post('/api/v1/subscriptions/create-order',headers=auth('patient'),json={'plan_name':'CLIENTE_PREMIUM','mobile':True,'amount':1})
    assert sub.status_code==200,sub.text
    assert [c['amount'] for c in calls]==[5,5,5]
    assert all(c['currency']=='USD' and c['return_url'].endswith('/payments/mobile-return') for c in calls)
    assert client.post('/api/v1/payments/capture',headers=auth('admin'),json={'paypal_order_id':online.json()['paypal_order_id']}).status_code==403
    assert client.get('/api/v1/payments',headers=auth('admin')).json()==[]
    assert client.get('/api/v1/payments/stats',headers=auth('admin')).json()['total_count']==0
    assert client.get('/api/v1/wallet',headers=auth('patient')).json()['balance']==0
    for method in ['EFECTIVO','PAYPAL']:
        web=client.post('/api/v1/payments/create',headers=auth('admin'),json={'tenant_id':'a','customer_name':'Cliente de caja','concept':'Servicio de caja','amount':37.5,'payment_method':method})
        assert web.status_code==200,web.text
        assert web.json()['amount']==37.5
    rows=client.get('/api/v1/payments',headers=auth('admin')).json()
    assert len(rows)==2
    assert all(p['purpose']=='POS' and p['cashier_id']=='admin' and p['amount']==37.5 for p in rows)
    assert {p['purpose'] for p in client.get('/api/v1/my-payments',headers=auth('patient')).json()}=={'CONSULTATION','WALLET_TOPUP'}
    stats=client.get('/api/v1/payments/stats',headers=auth('admin')).json()
    assert stats['total_collected']==37.5 and stats['total_count']==2


def test_cashier_consultation_paypal_belongs_only_to_web(client, db_session, setup, monkeypatch):
    accept(client)
    monkeypatch.setattr(PayPalService,'create_order',staticmethod(lambda **kw: {'order_id':'CASHIER','approval_url':'https://www.sandbox.paypal.com/checkoutnow?token=CASHIER'}))
    assert client.post('/api/v1/appointments/appointment/pay',headers=auth('admin'),json={'method':'PAYPAL'}).status_code==200
    rows=client.get('/api/v1/payments',headers=auth('admin')).json()
    assert len(rows)==1 and rows[0]['cashier_id']=='admin'
    assert client.get('/api/v1/my-payments',headers=auth('patient')).json()==[]
    assert client.post('/api/v1/payments/capture',headers=auth('patient'),json={'paypal_order_id':'CASHIER'}).status_code==403
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda order: completed(5)))
    assert client.post('/api/v1/payments/capture',headers=auth('admin'),json={'paypal_order_id':'CASHIER'}).status_code==200
    assert client.get('/api/v1/appointments',headers=auth('patient')).json()[0]['payment_status']=='PAID'


def test_cancel_payment_choice_allows_reselection_and_retires_old_order(client, db_session, setup, monkeypatch):
    accept(client)
    requests=[]
    def create(**kw):
        requests.append(kw['request_id'])
        return {'order_id':f'ORDER-{len(requests)}','approval_url':'https://www.sandbox.paypal.com/checkoutnow?token=NEW'}
    monkeypatch.setattr(PayPalService,'create_order',staticmethod(create))
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda _: {'status':'PAYER_ACTION_REQUIRED'}))
    path='/api/v1/appointments/appointment'
    assert client.post(path+'/pay',headers=auth('patient'),json={'method':'ONLINE'}).status_code==200
    assert client.post(path+'/cancel-payment-choice',headers=auth('other')).status_code==404
    assert client.post(path+'/cancel-payment-choice',headers=auth('patient')).status_code==200
    payment=db_session.query(Payment).one()
    assert payment.payment_method=='PENDING' and payment.paypal_order_id is None
    assert 'ORDER-1' in payment.notes
    assert client.post('/api/v1/payments/capture',headers=auth('patient'),json={'paypal_order_id':'ORDER-1'}).status_code==404
    assert client.post(path+'/pay',headers=auth('patient'),json={'method':'PRESENCIAL'}).status_code==200
    assert client.post(path+'/cancel-payment-choice',headers=auth('patient')).status_code==200
    assert client.post(path+'/pay',headers=auth('patient'),json={'method':'ONLINE'}).status_code==200
    assert len(set(requests))==2
    assert payment.paypal_order_id=='ORDER-2'


def test_cancel_after_paypal_approval_settles_original_without_second_charge(client, db_session, setup, monkeypatch):
    accept(client)
    monkeypatch.setattr(PayPalService,'create_order',staticmethod(lambda **kw: {'order_id':'APPROVED','approval_url':'https://www.sandbox.paypal.com/checkoutnow?token=APPROVED'}))
    path='/api/v1/appointments/appointment'
    assert client.post(path+'/pay',headers=auth('patient'),json={'method':'ONLINE'}).status_code==200
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(lambda _: completed(5)))
    response=client.post(path+'/cancel-payment-choice',headers=auth('patient'))
    assert response.status_code==200 and response.json()['status']=='COMPLETED'
    assert db_session.query(Payment).one().paypal_order_id=='APPROVED'
    assert db_session.query(WalletMovement).count()==0
    assert client.post(path+'/cancel-payment-choice',headers=auth('patient')).status_code==409


def test_cancel_choice_on_provider_failure_keeps_order(client, db_session, setup, monkeypatch):
    accept(client)
    payment=db_session.query(Payment).one()
    payment.paypal_order_id='KEEP'
    payment.payment_method='PAYPAL'
    db_session.commit()
    def unavailable(_): raise RuntimeError('offline')
    monkeypatch.setattr(PayPalService,'get_order',staticmethod(unavailable))
    response=client.post('/api/v1/appointments/appointment/cancel-payment-choice',headers=auth('patient'))
    assert response.status_code==502
    assert payment.paypal_order_id=='KEEP'


def test_push_queues_only_committed_notifications(client, db_session, setup, monkeypatch):
    from app.models.notification import Notification
    from app.services.push_service import PushService
    queued=[]
    monkeypatch.setattr(PushService,'enqueue',staticmethod(lambda ids: queued.extend(ids)))
    row=Notification(user_id='patient',tenant_id='a',title='Prueba',message='Mensaje',type='SISTEMA')
    db_session.add(row)
    db_session.flush()
    assert queued==[]
    db_session.rollback()
    assert queued==[]
    row=Notification(user_id='patient',tenant_id='a',title='Prueba',message='Mensaje',type='SISTEMA')
    db_session.add(row)
    db_session.commit()
    assert queued==[row.id]


def test_unregister_token_never_removes_another_accounts_device(client, db_session, setup):
    from app.models.ai_nutrition import DeviceToken
    db_session.add(DeviceToken(user_id='patient',token='patient-device-token',platform='android'))
    db_session.commit()
    path='/api/v1/automation/device-tokens/unregister'
    assert client.post(path,headers=auth('other'),json={'token':'patient-device-token'}).status_code==200
    assert db_session.query(DeviceToken).count()==1
    assert client.post(path,headers=auth('patient'),json={'token':'patient-device-token'}).status_code==200
    assert db_session.query(DeviceToken).count()==0


def test_push_payload_targets_owner_and_includes_unread_badge(db_session, setup, monkeypatch):
    import firebase_admin
    from firebase_admin import messaging
    import app.database as database
    from sqlalchemy.orm import sessionmaker
    from app.models.notification import Notification
    from app.models.ai_nutrition import DeviceToken
    from app.services.push_service import PushService
    monkeypatch.setattr(PushService,'enqueue',staticmethod(lambda _: None))
    db_session.add_all([DeviceToken(user_id='patient',token='owner-token',platform='android'),
                        DeviceToken(user_id='other',token='other-token',platform='android')])
    row=Notification(user_id='patient',tenant_id='a',title='Pago recibido',message='USD 5 wallet',type='PAGO')
    db_session.add(row)
    db_session.commit()
    monkeypatch.setattr(database,'get_session_local',lambda: sessionmaker(bind=db_session.bind))
    monkeypatch.setattr(firebase_admin,'get_app',lambda name: object())
    messages=[]
    monkeypatch.setattr(messaging,'send',lambda message,app=None: messages.append(message))
    PushService.deliver([row.id])
    assert len(messages)==1
    sent=messages[0]
    assert sent.token=='owner-token'
    assert sent.notification.title=='Pago recibido'
    assert sent.data['unread_count']=='1'
    assert sent.android.notification.notification_count==1
    assert sent.apns.payload.aps.badge==1
