from decimal import Decimal
from io import BytesIO
from xml.sax.saxutils import escape
from sqlalchemy.orm import Session
from app.config import settings
from app.models.subscription_receipt import SubscriptionReceipt
from app.models.user import User


class SubscriptionReceiptService:
    @staticmethod
    def issue(db: Session, subscription):
        """Called within the activation transaction, only after provider verification."""
        existing = db.get(SubscriptionReceipt, subscription.id)
        if existing:
            return existing
        if not subscription.paypal_capture_id or not subscription.started_at or not subscription.user_id:
            raise ValueError("El comprobante requiere un cobro confirmado y un comprador.")
        buyer = db.get(User, subscription.user_id)
        if not buyer:
            raise ValueError("Comprador no encontrado.")
        receipt = SubscriptionReceipt(
            id=subscription.id, user_id=buyer.id, buyer_name=buyer.full_name, buyer_email=buyer.email,
            plan_name=subscription.plan_name, amount=Decimal(str(subscription.amount)).quantize(Decimal("0.01")),
            currency=subscription.currency, paypal_order_id=subscription.paypal_order_id,
            paypal_capture_id=subscription.paypal_capture_id,
            is_sandbox="sandbox" in settings.PAYPAL_BASE_URL.lower(),
            paid_at=subscription.started_at, expires_at=subscription.expires_at,
        )
        db.add(receipt)
        return receipt

    @staticmethod
    def generate_pdf(receipt):
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
        stream = BytesIO()
        doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=42, leftMargin=42, topMargin=40, bottomMargin=40,
                                title="Comprobante de suscripción NutriSalud", author="NutriSalud")
        styles = getSampleStyleSheet()
        styles.add(ParagraphStyle(name="ReceiptTitle", fontSize=22, leading=28, textColor=colors.HexColor("#176443"), spaceAfter=12))
        styles.add(ParagraphStyle(name="ReceiptBody", fontSize=10, leading=15, spaceAfter=8))
        def p(value, style="ReceiptBody"):
            return Paragraph(escape(str(value)), styles[style])
        def stamp(value):
            return value.strftime("%d/%m/%Y %H:%M UTC") if value else "-"
        story = [p("NutriSalud", "ReceiptTitle"), p("COMPROBANTE DE PAGO DE SUSCRIPCIÓN", "Heading2"),
                 p(f"N.º NS-{receipt.id}"), p(f"Emitido: {stamp(receipt.issued_at)}")]
        if receipt.is_sandbox:
            story += [p("PAYPAL SANDBOX - PAGO DE PRUEBA. No acredita un cobro de dinero real.", "Heading3")]
        story += [Spacer(1, 14), p("Datos del comprador", "Heading3"), p(receipt.buyer_name), p(receipt.buyer_email),
                  Spacer(1, 10)]
        description = "Suscripción Premium IA - 30 días" if receipt.plan_name == "CLIENTE_PREMIUM" else f"Suscripción {receipt.plan_name} - 30 días"
        rows = [[p("Concepto"), p("Importe")], [p(description), p(f"{receipt.amount:.2f} {receipt.currency}")],
                [p("TOTAL PAGADO"), p(f"{receipt.amount:.2f} {receipt.currency}")]]
        table = Table(rows, colWidths=[365, 145], hAlign="LEFT")
        table.setStyle(TableStyle([("BACKGROUND", (0,0), (-1,0), colors.HexColor("#EAF4EE")),
            ("BACKGROUND", (0,-1), (-1,-1), colors.HexColor("#EAF4EE")),
            ("VALIGN", (0,0), (-1,-1), "TOP"), ("BOX", (0,0), (-1,-1), .5, colors.HexColor("#C8D8CE")),
            ("LEFTPADDING", (0,0), (-1,-1), 12), ("RIGHTPADDING", (0,0), (-1,-1), 12),
            ("TOPPADDING", (0,0), (-1,-1), 10), ("BOTTOMPADDING", (0,0), (-1,-1), 8)]))
        story += [table, Spacer(1, 18), p(f"Fecha del pago: {stamp(receipt.paid_at)}"),
                  p(f"Vigencia hasta: {stamp(receipt.expires_at)}"), p("Método de pago: PayPal"),
                  p(f"Orden PayPal: {receipt.paypal_order_id}"), p(f"Transacción / captura: {receipt.paypal_capture_id}"),
                  Spacer(1, 20), p("Este recibo registra el pago confirmado de la suscripción. No es una factura fiscal. "
                  "La vigencia actual de tu membresía se consulta en Suscripciones; cancelar o renovar no elimina este comprobante.")]
        doc.build(story)
        stream.seek(0)
        return stream
