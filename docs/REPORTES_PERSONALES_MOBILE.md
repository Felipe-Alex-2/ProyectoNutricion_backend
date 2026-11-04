# Alimentación, fotos IA y reportes personales en mobile

En Suscripciones se muestran accesos sin candado a Alimentación y fotos IA y Mis reportes, disponibles también para cuentas gratuitas y sin depender de la resolución de la suscripción. La primera reutiliza el diario mobile: plan, registro manual con sincronización offline, historial y análisis de fotografías. El análisis requiere conexión y la configuración Gemini existente.

Mis reportes permite elegir Alimentación y fotos IA, Citas, Pagos y recargas o Pagos de suscripción; filtrar fechas, consultar filas y descargar PDF o Excel. GET /api/v1/reports/mine y GET /api/v1/reports/mine/export calculan siempre el dueño desde el usuario autenticado; no reciben un patient_id ni permiten ampliar el alcance a otra clínica/cuenta. Los reportes administrativos web conservan sus permisos de personal. No se amplían permisos globales para clientes.

Los pagos y recargas se distinguen por concepto, sin sumar saldo anticipado y gasto de consultas en un total ambiguo. Los reportes muestran como máximo 500 filas e indican si hace falta reducir el rango. La fecha de alimentación corresponde al registro; la de citas corresponde a la cita y la de pagos al pago confirmado. Los reportes no son comprobantes de pago: cada pago cuenta con su recibo en Mis comprobantes.

Validación: pruebas de acceso gratuito, exclusión de datos de otra cuenta, fechas inválidas, exportación PDF/Excel y recibos individuales con descargas autenticadas. Las pruebas de interfaz abren ambos apartados desde una cuenta gratuita, llegan al análisis de fotos y consultan el detalle de un recibo sin iniciar una compra.
