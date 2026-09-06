import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
from app.config import settings

logger = logging.getLogger("email_service")


class EmailService:
    @staticmethod
    def send_password_reset_email(to_email: str, reset_token: str) -> bool:
        """Send a password reset email with a 10-minute expiration token."""
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={reset_token}"
        subject = "Recupera tu contraseña - NutriSalud"

        # HTML Email Template with NutriSalud Aesthetics (Forest Green & Warm Cream)
        html_content = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>Restablecer Contraseña</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: #F4EBD9;
      margin: 0;
      padding: 30px 15px;
      color: #172920;
    }}
    .container {{
      max-width: 520px;
      margin: 0 auto;
      background: #FFFFFF;
      border-radius: 20px;
      padding: 36px 30px;
      box-shadow: 0 4px 20px rgba(60, 48, 30, 0.08);
    }}
    .logo {{
      text-align: center;
      margin-bottom: 24px;
    }}
    .logo-badge {{
      display: inline-block;
      background: #206443;
      color: #FFFFFF;
      font-size: 20px;
      font-weight: 800;
      padding: 8px 18px;
      border-radius: 12px;
    }}
    h1 {{
      font-size: 22px;
      color: #172920;
      text-align: center;
      margin: 0 0 12px 0;
    }}
    p {{
      font-size: 15px;
      line-height: 1.6;
      color: #65756B;
      margin: 0 0 20px 0;
    }}
    .btn-container {{
      text-align: center;
      margin: 28px 0;
    }}
    .btn {{
      display: inline-block;
      background-color: #206443;
      color: #FFFFFF !important;
      text-decoration: none;
      padding: 14px 28px;
      font-size: 15px;
      font-weight: 700;
      border-radius: 12px;
    }}
    .token-box {{
      background-color: #F4EBD9;
      border: 1px dashed #206443;
      border-radius: 12px;
      padding: 14px;
      text-align: center;
      margin: 20px 0;
    }}
    .token-code {{
      font-family: monospace;
      font-size: 13px;
      font-weight: 700;
      color: #206443;
      word-break: break-all;
    }}
    .warning {{
      font-size: 13px;
      color: #E0873E;
      font-weight: 600;
      text-align: center;
    }}
    .footer {{
      margin-top: 30px;
      padding-top: 20px;
      border-top: 1px solid #EEEEEE;
      text-align: center;
      font-size: 12px;
      color: #8E9E94;
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="logo">
      <div class="logo-badge">🌿 NutriSalud</div>
    </div>
    <h1>Recuperación de Contraseña</h1>
    <p>Hola, recibimos una solicitud para restablecer la contraseña de tu cuenta asociada a <strong>{to_email}</strong>.</p>
    <p>Haz clic en el siguiente botón para elegir una nueva contraseña:</p>
    <div class="btn-container">
      <a href="{reset_link}" class="btn" target="_blank">Restablecer mi Contraseña</a>
    </div>
    <p style="font-size: 13px; text-align: center;">O copia este enlace en tu navegador:</p>
    <p style="font-size: 12px; word-break: break-all; text-align: center; color: #206443;"><a href="{reset_link}">{reset_link}</a></p>
    <div class="token-box">
      <div style="font-size: 12px; color: #65756B; margin-bottom: 6px;">Tu token de recuperación:</div>
      <div class="token-code">{reset_token}</div>
    </div>
    <div class="warning">
      ⏱️ Este token y enlace expirarán en <strong>10 minutos</strong>.
    </div>
    <div class="footer">
      Si no solicitaste este cambio, puedes ignorar este mensaje de forma segura. Tu contraseña actual no cambiará.<br><br>
      © 2026 NutriSalud. Todos los derechos reservados.
    </div>
  </div>
</body>
</html>
"""

        # Log details to console / logger for development visibility
        logger.info("=" * 65)
        logger.info(f"📧 [EMAIL DE RECUPERACIÓN - NUTRISALUD]")
        logger.info(f"Para: {to_email}")
        logger.info(f"Enlace de restablecimiento: {reset_link}")
        logger.info(f"Token (10 min de vigencia): {reset_token}")
        logger.info("=" * 65)

        # If SMTP settings are configured, deliver via SMTP
        if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
            try:
                msg = MIMEMultipart("alternative")
                msg["Subject"] = subject
                msg["From"] = f"{settings.EMAILS_FROM_NAME} <{settings.EMAILS_FROM_EMAIL}>"
                msg["To"] = to_email

                text_content = f"Recupera tu contraseña en NutriSalud:\n\nEnlace: {reset_link}\n\nToken: {reset_token}\n\nVálido por 10 minutos."
                msg.attach(MIMEText(text_content, "plain"))
                msg.attach(MIMEText(html_content, "html"))

                with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                    server.starttls()
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    server.sendmail(settings.EMAILS_FROM_EMAIL, to_email, msg.as_string())
                logger.info(f"✅ Correo enviado exitosamente vía SMTP a {to_email}")
                return True
            except Exception as e:
                logger.error(f"❌ Error al enviar correo vía SMTP: {e}")
                return False

        # In development without SMTP, return True so the flow succeeds and logs the token
        return True
