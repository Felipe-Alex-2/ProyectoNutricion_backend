import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
from sqlalchemy import delete
from app.models.user import User
from app.models.tenant import Tenant
from app.models.rbac import Role
from app.models.payment import Payment
from app.models.appointment import Appointment
from app.models.activity_log import ActivityLog
from app.models.generated_report import GeneratedReport
from app.services.backup_service import BackupService
from app.services.backup_recovery_service import BackupRecoveryService, canonical
from app.core.security import hash_password, create_access_token

@pytest.fixture
def context(db_session):
    for role in ['SUPERADMIN','ADMIN_ORGANIZATION','NUTRICIONISTA','CLIENTE']:
        db_session.add(Role(id=role,name=role,description=role,platform='Web'))
    db_session.add_all([Tenant(id='a',name='Company A',code='A'),Tenant(id='b',name='Company B',code='B')]);db_session.commit()
    users={}
    for uid,role,company in [('root','SUPERADMIN',None),('admin','ADMIN_ORGANIZATION','a'),('adminb','ADMIN_ORGANIZATION','b'),('doctor','NUTRICIONISTA','a'),('patient','CLIENTE','a')]:
        users[uid]=User(id=uid,email=uid+'@example.com',full_name=uid,hashed_password=hash_password('Password123!'),role_id=role,tenant_id=company,is_active=True)
        db_session.add(users[uid])
    db_session.commit();return users

def headers(uid):return {'Authorization':'Bearer '+create_access_token(subject=uid)}
def backup(db):return Path(BackupService.create_backup(db,tenant_id='a')['filepath']).read_bytes()
def preview(client,content,user='admin',company='a'):
    return client.post('/api/v1/backup/preview',headers=headers(user),params={'tenant_id':company},files={'file':('copy.json',content,'application/json')})
def restore(client,content,token,password='Password123!',user='admin',company='a'):
    return client.post('/api/v1/backup/restore',headers=headers(user),params={'tenant_id':company},files={'file':('copy.json',content,'application/json')},data={'review_token':token,'password':password})
def pay(db,identity='paid',company='a',status='COMPLETED',order=None):
    row=Payment(id=identity,tenant_id=company,customer_name='Patient',concept='Consulta',amount=20,status=status,paypal_order_id=order)
    db.add(row);db.commit();return row

def test_partial_restore_preview_password_and_no_duplicate(client,db_session,context):
    pay(db_session,'keep');pay(db_session,'recover');pay(db_session,'pending',status='PENDING');pay(db_session,'foreign',company='b')
    content=backup(db_session)
    db_session.execute(delete(Payment).where(Payment.id=='recover'));db_session.commit()
    p=preview(client,content);assert p.status_code==200,p.text
    assert p.json()['missing']==1 and p.json()['existing']==1
    assert db_session.get(Payment,'recover') is None
    denied=restore(client,content,p.json()['review_token'],password='WrongPassword!');assert denied.status_code==401
    assert db_session.get(Payment,'recover') is None
    r=restore(client,content,p.json()['review_token']);assert r.status_code==200,r.text
    assert r.json()['records_restored']==1
    assert db_session.query(Payment).count()==4
    p2=preview(client,content).json();assert p2['missing']==0
    assert restore(client,content,p2['review_token']).status_code==200
    assert db_session.query(Payment).count()==4

def test_changed_database_file_scope_and_actor_require_new_preview(client,db_session,context):
    pay(db_session);content=backup(db_session);p=preview(client,content).json()
    db_session.execute(delete(Payment));db_session.commit()
    assert restore(client,content,p['review_token']).status_code==409
    assert preview(client,content,user='adminb',company='a').status_code==403
    assert preview(client,content,user='root',company='b').status_code==400
    assert restore(client,content,p['review_token'],user='root').status_code==409
    assert preview(client,content,user='patient').status_code==403

def test_business_key_deduplicates_inside_file_and_existing_database(client,db_session,context):
    pay(db_session,order='order1');content=backup(db_session)
    snap=BackupRecoveryService.parse(content,'a');row=dict(snap['tables']['payments'][0]);row['id']='different-id';snap['tables']['payments'].append(row)
    db_session.execute(delete(Payment));db_session.commit()
    plan=BackupRecoveryService.build_plan(db_session,snap)
    assert plan['missing']==1 and plan['existing']==1
    db_session.add(Payment(id='already-here',tenant_id='a',customer_name='Keep',concept='Keep',amount=99,status='COMPLETED',paypal_order_id='order1'));db_session.commit()
    plan=BackupRecoveryService.build_plan(db_session,snap);assert plan['missing']==0 and plan['existing']==2
    assert db_session.get(Payment,'already-here').amount==99

def test_missing_dependency_is_skipped_and_cross_company_reference_rejected(db_session,context):
    row=pay(db_session);row.cashier_id='admin';db_session.commit();snap=BackupRecoveryService.parse(backup(db_session),'a')
    db_session.execute(delete(Payment));db_session.commit()
    snap['tables']['payments'][0]['cashier_id']='deleted-user'
    plan=BackupRecoveryService.build_plan(db_session,snap);assert plan['missing']==0 and plan['skipped']==1
    snap['tables']['payments'][0]['cashier_id']='adminb'
    with pytest.raises(ValueError,match='otra empresa'):BackupRecoveryService.build_plan(db_session,snap)

def test_audit_records_only_mutations_without_ip(client,db_session,context):
    nav=client.post('/api/v1/activity-logs',headers=headers('admin'),json={'action':'NAVEGACION','description':'Open payments','category':'SYSTEM'})
    assert nav.status_code==400
    row=pay(db_session)
    # An authenticated mutation is captured automatically, even without a browser log.
    db_session.info['audit_actor']=context['admin'];row.concept='Changed';db_session.commit()
    logs=client.get('/api/v1/activity-logs',headers=headers('admin')).json()
    assert any('ACTUALIZADO' in log['action'] for log in logs)
    assert all('ip_address' not in log for log in logs)
    assert all(log.ip_address is None for log in db_session.query(ActivityLog))

def test_completed_appointments_and_saved_reports_in_backup(client,db_session,context):
    for identity,status in [('done','CONFIRMED'),('pending','PENDING')]:
        db_session.add(Appointment(id=identity,tenant_id='a',patient_id='patient',nutritionist_id='doctor',status=status,scheduled_at=datetime.now(timezone.utc)-timedelta(days=1)))
    db_session.commit()
    assert client.post('/api/v1/appointments/done/complete',headers=headers('patient')).status_code==403
    r=client.post('/api/v1/appointments/done/complete',headers=headers('doctor'));assert r.status_code==200,r.text
    assert r.json()['completed_at']
    assert client.post('/api/v1/appointments/done/cancel',headers=headers('admin')).status_code==400
    assert client.post('/api/v1/appointments/done/confirm',headers=headers('admin')).status_code==400
    saved=client.post('/api/v1/reports/saved',headers=headers('admin'),json={'entity':'payments','columns':[]});assert saved.status_code==201,saved.text
    identity=saved.json()['id']
    assert client.get('/api/v1/reports/saved/'+identity,headers=headers('adminb')).status_code==403
    snap=BackupRecoveryService.parse(backup(db_session),'a')
    assert [r['id'] for r in snap['tables']['appointments']]==['done']
    assert [r['id'] for r in snap['tables']['generated_reports']]==[identity]

def test_create_company_assign_admin_branches_and_register(client,db_session,context):
    candidate=client.post('/api/v1/tenants/administrator-candidates',headers=headers('root'),json={'full_name':'New Admin','email':'new@example.com','password':'Password123!'});assert candidate.status_code==201,candidate.text
    body={'name':'New Company','code':'NEW','administrator_id':candidate.json()['id'],'initial_branch_name':'Centro'}
    assert client.post('/api/v1/tenants',headers=headers('admin'),json=body).status_code==403
    created=client.post('/api/v1/tenants',headers=headers('root'),json=body);assert created.status_code==201,created.text
    company=created.json()['id'];user=db_session.get(User,candidate.json()['id']);assert user.tenant_id==company and user.branch_id
    assert client.post('/api/v1/tenants',headers=headers('root'),json={**body,'name':'Another','code':'OTHER'}).status_code==400
    branches=client.get('/api/v1/branches/public',params={'tenant_id':company}).json();assert len(branches)==1
    assert client.post('/api/v1/branches',headers=headers('admin'),json={'tenant_id':company,'name':'Attack','code':'AT'}).status_code==403
    public=client.get('/api/v1/tenants/public').json();assert any(t['id']==company for t in public)
    assert all('administrator_id' not in t and 'users_count' not in t for t in public)
    registration={'full_name':'New Patient','email':'newpatient@example.com','password':'Password123!','tenant_id':company,'branch_id':branches[0]['id']}
    assert client.post('/api/v1/auth/register',json={**registration,'tenant_id':'a'}).status_code==400
    r=client.post('/api/v1/auth/register',json=registration);assert r.status_code==201,r.text
    patient=db_session.query(User).filter_by(email=registration['email']).one();assert patient.tenant_id==company and patient.branch_id==branches[0]['id'] and patient.role_id=='CLIENTE'
