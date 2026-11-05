from datetime import datetime, timedelta, timezone
from tests.test_reporting_analytics import reporting, headers, query, voice
from tests.test_workspace_scope import workspaces, auth
from app.models.patient_link import PatientNutritionistLink
from app.models.ai_nutrition import FoodRecord


def test_clients_use_general_reports_without_cross_company_access(client, reporting):
    data=query(client,'p1',entity='patients')
    assert data.status_code==200,data.text
    assert {r['full_name'] for r in data.json()['rows']}=={'p1','p2','p3'}
    for entity in ['recipes','appointments','payments','clinical_records','activity_logs','nutritional_plans']:
        response=query(client,'p1',entity=entity)
        assert response.status_code==200,response.text
    assert query(client,'p1',entity='patients',tenant_id='beta').status_code==403
    assert query(client,'p1',entity='patients',branch_ids=['b1']).status_code==403
    result=voice(client,'Clientes activos','p1')
    assert result.status_code==200,result.text
    for kind,signature in [('pdf',b'%PDF'),('excel',b'PK')]:
        response=client.post('/api/v1/reports/export/'+kind,headers=headers('p1'),json={'entity':'patients','columns':['full_name']})
        assert response.status_code==200,response.text[:300]
        assert response.content.startswith(signature)


def test_linked_superadmin_is_available_and_accepts_appointments(client,db_session,workspaces):
    db_session.add(PatientNutritionistLink(id='link-root',nutritionist_id='root',patient_id='p1',tenant_id='a',pairing_code='NUTRI-12345',whatsapp_number='123',status='LINKED',linked_at=datetime.now(timezone.utc)))
    db_session.commit()
    available=client.get('/api/v1/appointments/nutritionists',headers=auth('p1'))
    assert available.status_code==200,available.text
    assert 'root' in {r['id'] for r in available.json()}
    body={'nutritionist_id':'root','tenant_id':'a','branch_id':'a1','scheduled_at':(datetime.now(timezone.utc)+timedelta(days=2)).isoformat(),'reason':'Consulta'}
    created=client.post('/api/v1/appointments',headers=auth('p1'),json=body)
    assert created.status_code==200,created.text
    assert created.json()['tenant_id']=='a'
    assert client.post('/api/v1/appointments',headers=auth('p2'),json=body).status_code==403
    confirmed=client.post('/api/v1/appointments/'+created.json()['id']+'/confirm',headers=auth('root'))
    assert confirmed.status_code==200,confirmed.text
    assert confirmed.json()['status']=='ACCEPTED'


def test_clinical_food_history_requires_link_and_returns_mobile_analysis(client,db_session,workspaces):
    db_session.add(PatientNutritionistLink(id='link-food',nutritionist_id='doctor',patient_id='p1',tenant_id='a',pairing_code='NUTRI-54321',whatsapp_number='123',status='LINKED'))
    db_session.add(FoodRecord(id='food',patient_id='p1',result_json='{"description":"Arroz y pollo"}',estimated_calories=400,estimated_carbs=40,estimated_protein=30,estimated_fats=10,confidence='high'))
    db_session.commit()
    response=client.get('/api/v1/food/history?patient_id=p1',headers=auth('doctor'))
    assert response.status_code==200,response.text
    assert response.json()[0]['details']['description']=='Arroz y pollo'
    assert client.get('/api/v1/food/history?patient_id=p3',headers=auth('doctor')).status_code in (403,404)



def test_client_saved_snapshot_exports_and_stays_owned(client,reporting):
    saved=client.post('/api/v1/reports/saved',headers=headers('p1'),json={'entity':'patients','columns':['full_name']})
    assert saved.status_code==201,saved.text
    identity=saved.json()['id']
    for fmt,signature in [('pdf',b'%PDF'),('excel',b'PK')]:
        response=client.get(f'/api/v1/reports/saved/{identity}/export?file_format={fmt}',headers=headers('p1'))
        assert response.status_code==200,response.text
        assert response.content.startswith(signature)
    assert client.get(f'/api/v1/reports/saved/{identity}/export',headers=headers('p2')).status_code==403


def test_mobile_all_roles_compare_companies_and_export(client,reporting):
    for who in ['p1','doctor','admin','root']:
        mobile={**headers(who),'X-Report-Client':'mobile'}
        scope=client.get('/api/v1/reports/scope',headers=mobile)
        assert scope.status_code==200,scope.text
        assert {c['id'] for c in scope.json()['companies']}=={'alpha','beta','empty'}
        result=client.post('/api/v1/reports/voice-command',headers=mobile,json={'transcript':'Qué empresa tiene más clientes'})
        assert result.status_code==200,result.text
        assert len(result.json()['report_data']['rows'])==3
        request=result.json()['parsed_request']
        for fmt,signature in [('pdf',b'%PDF'),('excel',b'PK')]:
            exported=client.post('/api/v1/reports/export/'+fmt,headers=mobile,json=request)
            assert exported.status_code==200,exported.text[:300]
            assert exported.content.startswith(signature)
        saved=client.post('/api/v1/reports/saved',headers=mobile,json=request)
        assert saved.status_code==201,saved.text
        downloaded=client.get('/api/v1/reports/saved/'+saved.json()['id']+'/export',headers=mobile)
        assert downloaded.status_code==200,downloaded.text
