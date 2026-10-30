"""Company-scoped, insert-only recovery of operational records."""
import gzip
import hashlib
import io
import json
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from jose import jwt, JWTError
from sqlalchemy import select, and_, UniqueConstraint
from sqlalchemy.types import DateTime, Date, Numeric
from app.database import Base
from app.config import settings

MAX_BYTES = 32 * 1024 * 1024
TABLES = {'payments': 'Cobros confirmados', 'recipes': 'Recetas del plan', 'recipe_assignments': 'Asignaciones de recetas', 'nutritional_plans': 'Planes nutricionales', 'appointments': 'Citas atendidas', 'activity_logs': 'Bitácora de operaciones', 'generated_reports': 'Reportes guardados'}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, default=lambda v: v.isoformat() if isinstance(v, (datetime, date)) else str(v))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result: raise ValueError('El archivo contiene claves JSON repetidas.')
        result[key] = value
    return result


class BackupRecoveryService:
    @staticmethod
    def parse(content, tenant_id):
        from app.services.backup_service import BackupService
        if isinstance(content, bytes):
            if len(content) > MAX_BYTES: raise ValueError('El archivo supera 32 MB.')
            if content.startswith(b'\x1f\x8b'):
                with gzip.GzipFile(fileobj=io.BytesIO(content)) as stream: content = stream.read(MAX_BYTES + 1)
            if len(content) > MAX_BYTES: raise ValueError('El archivo descomprimido supera 32 MB.')
            content = json.loads(content.decode('utf-8'), object_pairs_hook=unique_object)
        if not isinstance(content, dict) or content.get('format') != 'nutrisalud-encrypted-v2':
            raise ValueError('Selecciona un respaldo operativo de NutriSalud (versión 2). Los respaldos antiguos no se importan automáticamente.')
        try:
            plain = BackupService._cipher().decrypt(content['ciphertext'].encode())
            if len(plain) > MAX_BYTES: raise ValueError('El contenido supera 32 MB.')
            snapshot = json.loads(plain, object_pairs_hook=unique_object)
        except Exception as exc:
            raise ValueError('No se pudo verificar el respaldo: clave incorrecta, formato inválido o archivo alterado.') from exc
        if not isinstance(snapshot, dict): raise ValueError('Estructura de respaldo inválida.')
        if snapshot.get('format') != 'NUTRISALUD_OPERATIONAL_BACKUP' or snapshot.get('version') != 2:
            raise ValueError('Formato de respaldo no compatible.')
        if snapshot.get('tenant_id') != tenant_id: raise ValueError('El respaldo pertenece a otra empresa.')
        try: datetime.fromisoformat(snapshot.get('created_at', ''))
        except (ValueError, TypeError): raise ValueError('Fecha del respaldo inválida.')
        tables = snapshot.get('tables')
        if not isinstance(tables, dict) or not tables or set(tables) - set(TABLES): raise ValueError('El respaldo contiene tablas no permitidas.')
        total = 0
        for name, rows in tables.items():
            if not isinstance(rows, list): raise ValueError('Estructura de tabla inválida.')
            total += len(rows)
            for row in rows:
                if not isinstance(row, dict): raise ValueError('Registro inválido.')
                if set(row) - set(Base.metadata.tables[name].c.keys()): raise ValueError('El respaldo contiene columnas desconocidas.')
                if any(any(word in key.lower() for word in ('password', 'secret', 'token', 'ip_address')) for key in row): raise ValueError('El respaldo contiene datos de seguridad no permitidos.')
                if 'tenant_id' in Base.metadata.tables[name].c and row.get('tenant_id') != tenant_id: raise ValueError('El archivo mezcla empresas.')
                if name == 'payments' and row.get('status') != 'COMPLETED': raise ValueError('Solo se recuperan cobros confirmados.')
                if name == 'appointments' and row.get('status') != 'COMPLETED': raise ValueError('Solo se recuperan citas atendidas.')
        if total > 200000: raise ValueError('El respaldo supera 200.000 registros.')
        return snapshot

    @staticmethod
    def build_plan(db, snapshot):
        tenant_id = snapshot['tenant_id']
        from app.models.user import User
        from app.models.recipe import Recipe
        from app.models.tenant import Tenant
        if db.get(Tenant, tenant_id) is None: raise ValueError('La empresa debe existir antes de recuperar sus operaciones.')
        pending_unique = {}; mappings = {}; available = {}; operations = []; summary = []; warnings = []
        for table in Base.metadata.sorted_tables:
            if table.name not in TABLES: continue
            rows = snapshot['tables'].get(table.name, [])
            counts = {'table': table.name, 'label': TABLES[table.name], 'in_file': len(rows), 'missing': 0, 'existing': 0, 'skipped': 0}
            seen = set(); available.setdefault(table.name, set()); mappings.setdefault(table.name, {})
            for raw in rows:
                values = dict(raw); keys = list(table.primary_key.columns)
                key = tuple(values.get(c.name) for c in keys)
                reason = None; state = 'missing'
                if any(not isinstance(v, str) or not v for v in key): raise ValueError('Un registro no tiene una clave válida.')
                if key in seen: reason = 'Registro repetido en el archivo.'
                seen.add(key)
                predicate = and_(*(c == v for c,v in zip(keys,key)))
                existing = db.execute(select(table).where(predicate)).mappings().first()
                if existing:
                    owner = existing.get('tenant_id')
                    if 'tenant_id' in existing and owner != tenant_id: raise ValueError('Un identificador ya pertenece a otra empresa.')
                    if table.name == 'recipe_assignments':
                        recipe = db.get(Recipe, existing['recipe_id'])
                        if not recipe or recipe.tenant_id != tenant_id: raise ValueError('La asignación pertenece a otra empresa.')
                    state = 'existing'
                if not reason and state == 'missing':
                    for column in table.columns:
                        value = values.get(column.name)
                        if value is not None:
                            if isinstance(column.type, DateTime): values[column.name] = datetime.fromisoformat(value)
                            elif isinstance(column.type, Date): values[column.name] = date.fromisoformat(value)
                            elif isinstance(column.type, Numeric): values[column.name] = Decimal(str(value))
                        for foreign in column.foreign_keys:
                            target = foreign.column.table
                            if value is None: continue
                            value = mappings.get(target.name, {}).get(value, value); values[column.name] = value
                            if value in available.get(target.name, set()): continue
                            parent = db.execute(select(target).where(foreign.column == value)).mappings().first()
                            if parent is None: reason = f'Falta la relación {target.name}.'; break
                            owner = parent.get('tenant_id') if target.name != 'tenants' else parent['id']
                            if owner is not None and owner != tenant_id: raise ValueError('Una relación pertenece a otra empresa.')
                        if reason: break
                    if not reason:
                        unique_keys = [list(c.columns) for c in table.constraints if isinstance(c, UniqueConstraint)]
                        unique_keys += [[c] for c in table.columns if c.unique]
                        if table.name == 'recipe_assignments': unique_keys += [[table.c.recipe_id, table.c.patient_id]]
                        if table.name == 'payments': unique_keys += [[table.c.paypal_order_id], [table.c.paypal_capture_id]]
                        for cols in unique_keys:
                            if not all(values.get(c.name) is not None for c in cols): continue
                            signature = (table.name, tuple(c.name for c in cols), tuple(str(values[c.name]) for c in cols))
                            match = pending_unique.get(signature) or db.execute(select(table).where(and_(*(c == values[c.name] for c in cols)))).mappings().first()
                            if match:
                                if match.get('tenant_id', tenant_id) != tenant_id: raise ValueError('Una clave de negocio pertenece a otra empresa.')
                                state = 'existing'; existing = match; break
                    missing_fields = [c.name for c in table.columns if not c.nullable and not c.default and not c.server_default and values.get(c.name) is None]
                    if missing_fields and not reason: reason = 'Faltan campos obligatorios: ' + ', '.join(missing_fields)
                if reason:
                    state = 'skipped'
                    if len(warnings) < 30: warnings.append({'table': table.name, 'id': str(key[0]), 'reason': reason})
                else:
                    mapped_id = existing[keys[0].name] if existing else key[0]
                    mappings[table.name][key[0]] = mapped_id; available[table.name].add(mapped_id)
                if state == 'missing':
                    for cols in unique_keys:
                        if all(values.get(c.name) is not None for c in cols):
                            signature = (table.name, tuple(c.name for c in cols), tuple(str(values[c.name]) for c in cols))
                            pending_unique[signature] = values
                counts[state] += 1
                operations.append({'table': table.name, 'id': key, 'state': state, 'values': values if state == 'missing' else None})
            summary.append(counts)
        return {'tables': summary, 'warnings': warnings, 'missing': sum(s['missing'] for s in summary), 'existing': sum(s['existing'] for s in summary), 'skipped': sum(s['skipped'] for s in summary), 'operations': operations}

    @classmethod
    def preview(cls, db, content, tenant_id, actor):
        snapshot = cls.parse(content, tenant_id); plan = cls.build_plan(db, snapshot)
        claims = {'kind': 'backup_review', 'sub': actor.id, 'tenant_id': tenant_id, 'file_hash': digest(snapshot), 'plan_hash': digest(plan), 'exp': datetime.now(timezone.utc) + timedelta(minutes=15)}
        return {k:v for k,v in plan.items() if k != 'operations'} | {'tenant_id': tenant_id, 'created_at': snapshot['created_at'], 'review_token': jwt.encode(claims, settings.SECRET_KEY, algorithm=settings.ALGORITHM)}

    @classmethod
    def restore(cls, db, content, tenant_id, actor, review_token, password):
        from app.core.security import verify_password
        from app.core.exceptions import AuthException, ConflictException
        from app.models.activity_log import ActivityLog
        if not verify_password(password, actor.hashed_password): raise AuthException('La contraseña de tu cuenta es incorrecta.')
        try:
            claims = jwt.decode(review_token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError as exc: raise ConflictException('La revisión venció. Analiza el archivo otra vez.') from exc
        from app.models.tenant import Tenant
        db.execute(select(Tenant).where(Tenant.id == tenant_id).with_for_update()).scalar_one()
        snapshot = cls.parse(content, tenant_id); plan = cls.build_plan(db, snapshot)
        if claims.get('kind') != 'backup_review' or claims.get('sub') != actor.id or claims.get('tenant_id') != tenant_id or claims.get('file_hash') != digest(snapshot) or claims.get('plan_hash') != digest(plan): raise ConflictException('El archivo o los datos cambiaron. Analiza el respaldo otra vez.')
        restored = 0; names = set()
        try:
            for op in plan['operations']:
                if op['state'] != 'missing': continue
                db.execute(Base.metadata.tables[op['table']].insert().values(**op['values'])); restored += 1; names.add(op['table'])
            db.add(ActivityLog(tenant_id=tenant_id, user_id=actor.id, user_name=actor.full_name, user_email=actor.email, action='BACKUP_RESTAURADO', description=f'Se recuperaron {restored} registros faltantes; los existentes se conservaron.', category='SYSTEM'))
            db.commit()
        except Exception:
            db.rollback(); raise
        return {'success': True, 'message': f'Se recuperaron {restored} registros faltantes sin sobrescribir los existentes.', 'records_restored': restored, 'tables_restored': len(names)}
