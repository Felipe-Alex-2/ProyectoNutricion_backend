"""FCM delivery runs only after a notification transaction has committed."""
import logging
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from sqlalchemy import event
from sqlalchemy.orm import Session
from app.config import settings
from app.models.notification import Notification

logger = logging.getLogger('push')
_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix='fcm')
_app_lock = Lock()


class PushService:
    @staticmethod
    def configured():
        return bool(settings.FIREBASE_PROJECT_ID and settings.FIREBASE_CLIENT_EMAIL and settings.FIREBASE_PRIVATE_KEY)

    @staticmethod
    def enqueue(notification_ids):
        if PushService.configured():
            _executor.submit(PushService.deliver, tuple(notification_ids))

    @staticmethod
    def deliver(notification_ids):
        from app.database import get_session_local
        from app.models.ai_nutrition import DeviceToken
        import firebase_admin
        from firebase_admin import credentials, messaging
        try:
            with _app_lock:
                try:
                    app = firebase_admin.get_app('nutrisalud-push')
                except ValueError:
                    app = firebase_admin.initialize_app(credentials.Certificate({
                        'type': 'service_account', 'project_id': settings.FIREBASE_PROJECT_ID,
                        'client_email': settings.FIREBASE_CLIENT_EMAIL,
                        'private_key': settings.FIREBASE_PRIVATE_KEY.replace('\\n', '\n'),
                        'token_uri': 'https://oauth2.googleapis.com/token',
                    }), name='nutrisalud-push')
            with get_session_local()() as db:
                for notification_id in notification_ids:
                    notification = db.get(Notification, notification_id)
                    if notification is None or notification.is_read:
                        continue
                    count = db.query(Notification).filter_by(user_id=notification.user_id, is_read=False).count()
                    tokens = db.query(DeviceToken).filter_by(user_id=notification.user_id).all()
                    for token in tokens:
                        try:
                            messaging.send(messaging.Message(
                                token=token.token,
                                notification=messaging.Notification(title=notification.title, body=notification.message),
                                data={'notification_id': notification.id, 'user_id': notification.user_id,
                                      'reference_id': notification.reference_id or '', 'type': notification.type,
                                      'unread_count': str(count)},
                                android=messaging.AndroidConfig(priority='high', notification=messaging.AndroidNotification(
                                    channel_id='nutrisalud_messages', sound='default', notification_count=count,
                                    tag='nutrisalud-unread', icon='ic_stat_notification')),
                                apns=messaging.APNSConfig(payload=messaging.APNSPayload(aps=messaging.Aps(badge=count, sound='default'))),
                            ), app=app)
                        except messaging.UnregisteredError:
                            db.delete(token)
                        except Exception:
                            logger.exception('FCM delivery failed for notification %s', notification.id)
                db.commit()
        except Exception:
            logger.exception('Could not initialize or deliver Firebase push notifications')


@event.listens_for(Session, 'before_flush')
def remember_new_notifications(session, flush_context, instances):
    pending = session.info.setdefault('_push_new', [])
    pending.extend(row for row in session.new if isinstance(row, Notification) and row not in pending)


@event.listens_for(Session, 'after_commit')
def dispatch_committed_notifications(session):
    pending = session.info.pop('_push_new', [])
    ids = [row.id for row in pending if row.id]
    if ids:
        try:
            PushService.enqueue(ids)
        except Exception:
            logger.exception('Could not queue push notifications after commit')


@event.listens_for(Session, 'after_rollback')
def discard_rolled_back_notifications(session):
    session.info.pop('_push_new', None)
