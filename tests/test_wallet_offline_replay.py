from datetime import datetime, timedelta, timezone
from decimal import Decimal
from app.models.appointment import Appointment
from app.models.payment import Payment
from app.models.wallet import WalletMovement
from tests.test_consultation_wallet import setup, auth, accept


def test_wallet_replay_settles_once_and_revalidates_other_device_spending(client, db_session, setup):
    accept(client)
    db_session.add(Payment(id='credit', patient_id='patient', tenant_id='a', branch_id='a1',
        purpose='WALLET_TOPUP', customer_name='patient', concept='Recarga', amount=5,
        currency='USD', status='COMPLETED', payment_method='PAYPAL'))
    db_session.flush()
    db_session.add(WalletMovement(user_id='patient', tenant_id='a', branch_id='a1',
        payment_id='credit', amount=Decimal('5'), concept='Recarga'))
    db_session.add(Appointment(id='second', patient_id='patient', nutritionist_id='doctor',
        tenant_id='a', branch_id='a1', scheduled_at=datetime.now(timezone.utc) + timedelta(days=2), status='ACCEPTED'))
    db_session.commit()
    headers = {**auth('patient'), 'Idempotency-Key': 'offline-wallet-1'}
    for _ in range(2):
        response = client.post('/api/v1/appointments/appointment/pay', headers=headers,
            json={'method': 'WALLET', 'mobile': True})
        assert response.status_code == 200, response.text
        assert response.json()['status'] == 'COMPLETED'
    assert db_session.query(WalletMovement).filter(WalletMovement.amount < 0).count() == 1
    assert client.get('/api/v1/wallet', headers=auth('patient')).json()['balance'] == 0
    # Another device spent the last funds before a second offline intent arrived.
    rejected = client.post('/api/v1/appointments/second/pay', headers={**auth('patient'), 'Idempotency-Key': 'offline-wallet-2'},
        json={'method': 'WALLET', 'mobile': True})
    assert rejected.status_code == 400
    assert db_session.get(Appointment, 'second').status == 'ACCEPTED'
    assert db_session.query(WalletMovement).filter(WalletMovement.amount < 0).count() == 1
