"""One-shot scheduled job for all enabled backup configurations."""
from app.database import get_session_local
from app.models.backup import BackupSetting
from app.services.backup_service import BackupService

def run():
    with get_session_local()() as db:
        scopes = [row.tenant_id for row in db.query(BackupSetting).filter_by(auto_backup_enabled=True).all()]
        for tenant_id in scopes:
            if not tenant_id: continue
            BackupService.check_and_run_auto_backup(db, tenant_id=tenant_id)

if __name__ == "__main__":
    run()
