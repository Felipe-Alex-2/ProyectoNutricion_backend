from app.services.bolivia_locations import CATALOG, validate_location
from app.core.exceptions import BadRequestException
from app.models.tenant import Tenant
from app.models.company import Branch
from app.models.user import User
from app.models.rbac import Role
from app.core.security import create_access_token
import pytest


def test_catalog_codes_and_hierarchy():
    assert len(CATALOG) == 9
    codes = set()
    for department in CATALOG:
        for province in department['provinces']:
            for municipality in province['municipalities']:
                assert municipality['code'] not in codes
                codes.add(municipality['code'])
                assert municipality['code'].startswith(province['code'])
                assert province['code'].startswith(department['code'])
                validate_location(department['code'], province['code'], municipality['code'])
    validate_location('01', '0101', '010101')  # Chuquisaca / Oropeza / Sucre
    with pytest.raises(BadRequestException): validate_location('07', '0101', '010101')
    with pytest.raises(BadRequestException): validate_location('01', '0101', '070101')


def test_branch_location_validation_and_company_scope(client, db_session):
    db = db_session
    for role in ['SUPERADMIN', 'ADMIN_ORGANIZATION']:
        db.add(Role(id=role, name=role, description=role, platform='Web'))
    db.add_all([Tenant(id='chuq',name='Chuquisaca',code='CH',department_code='01'), Tenant(id='scz',name='Santa Cruz',code='SC',department_code='07')])
    db.flush()
    db.add_all([User(id='rootgeo',email='rootgeo@example.com',full_name='Root',hashed_password='unused',role_id='SUPERADMIN'), User(id='admingeo',email='admingeo@example.com',full_name='Admin',hashed_password='unused',role_id='ADMIN_ORGANIZATION',tenant_id='chuq')])
    db.commit()
    headers = {'Authorization': 'Bearer ' + create_access_token(subject='admingeo')}
    root = {'Authorization': 'Bearer ' + create_access_token(subject='rootgeo')}
    body = {'tenant_id':'chuq','name':'Sucre Centro','code':'CENTRO','province_code':'0101','municipality_code':'010101'}
    invalid = client.post('/api/v1/branches',headers=headers,json={**body,'province_code':'0701','municipality_code':'070101'})
    assert invalid.status_code == 400
    assert db.query(Branch).count() == 0
    created = client.post('/api/v1/branches',headers=headers,json=body)
    assert created.status_code == 201, created.text
    assert created.json()['municipality_code'] == '010101'
    branch_id = created.json()['id']
    assert client.put('/api/v1/branches/'+branch_id,headers=root,json={**body,'tenant_id':'scz'}).status_code == 400
    assert client.post('/api/v1/branches',headers=headers,json={**body,'tenant_id':'scz'}).status_code == 403
    assert client.put('/api/v1/tenants/chuq',headers=root,json={'department_code':'07'}).status_code == 400
    assert db.get(Tenant,'chuq').department_code == '01'
    updated = client.put('/api/v1/branches/'+branch_id,headers=headers,json={**body,'name':'Sucre Norte','municipality_code':'010102'})
    assert updated.status_code == 200, updated.text
    assert updated.json()['municipality_code'] == '010102'
