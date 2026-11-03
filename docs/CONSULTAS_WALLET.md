# Consulta general y wallet

## Flujo

1. El cliente solicita la consulta general desde móvil. Queda `PENDING`.
2. El equipo acepta desde Gestión de citas (`POST /appointments/{id}/confirm`, ruta conservada por compatibilidad). Pasa a `ACCEPTED`, crea un único cobro pendiente de USD 5 con paciente, empresa y sucursal de la cita.
3. El botón «Cobrar USD 5» abre la caja web con los datos del paciente. Se registra efectivo o se inicia PayPal. En móvil, el cliente tiene tres opciones directas después de la aceptación: Wallet, Online (PayPal Sandbox) y Presencial. Presencial notifica al equipo, conserva el cobro pendiente y muestra «Cobrar USD 5 en caja» en la cita; ese botón abre la caja con cliente, correo e importe precargados.
4. El cobro completado y el cambio a `CONFIRMED` se guardan en una transacción. Se notifica al paciente y se conserva el comprobante. La web consulta cambios cada 12 segundos y el móvil cada 15 segundos mientras está en primer plano.

Las citas confirmadas de versiones anteriores conservan su estado y no reciben cobros retroactivos.

## Wallet en Perfil

- Recarga fija: USD 5 por operación, exclusivamente por PayPal Sandbox. Otros importes se rechazan en backend.
- La solicitud incluye `Idempotency-Key`. La misma clave reanuda la operación original y rechaza un importe distinto.
- El saldo se obtiene del libro de movimientos decimales del paciente; no se modifica en el teléfono.
- Una recarga solo se acredita cuando PayPal devuelve captura `COMPLETED`, con importe y moneda coincidentes. Las verificaciones repetidas no vuelven a acreditar.
- Pagar una consulta debita USD 5 y confirma la cita en la misma transacción. Se bloquean saldo insuficiente, pacientes ajenos y cobros antes de aceptar.
- Al volver de PayPal, la app verifica automáticamente la orden activa (o la más reciente pendiente al abrir la pantalla). «Verificar pago» permite reintentar manualmente. Las órdenes pendientes y «Volver a abrir PayPal» permanecen disponibles desde Perfil aunque se cierre la pantalla.
- Los pagos mobile (recargas y consultas online/wallet) no aparecen en historial, estadísticas ni reportes de caja web. Caja muestra cobros POS con importe elegido por el cajero y consultas cobradas explícitamente por ese cajero. La cita conserva su estado pagado visible para el equipo, aunque el pago venga de mobile.

No se cambia a efectivo/wallet mientras exista una orden PayPal iniciada, para evitar dos cobros por la misma consulta. La devolución de una cita ya pagada requiere un proceso administrativo; este cambio no implementa reembolsos ni cancelaciones de pagos capturados.

## Despliegue

Desplegar primero backend y después web/móvil. La migración `20261031_08` añade referencias a paciente/cita y `purpose` a pagos, y crea `wallet_movements`. `railway.toml` ya ejecuta `python prepare_db.py` como predeploy; si Railway tiene otra configuración manual, conservar ese paso. No ejecutar SQL para simular saldo.

Se usan las variables PayPal existentes (`PAYPAL_CLIENT_ID`, `PAYPAL_CLIENT_SECRET`, `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`) y `FRONTEND_URL` real para retornos de caja web. El retorno móvil es `/api/v1/payments/mobile-return`: invita a volver a la app; no acredita pagos con parámetros de URL.

Las pruebas usan respuestas PayPal simuladas. Antes de dar por operativo el despliegue, realizar una recarga con comprador Sandbox y pagar una cita aceptada; comprobar saldo, historial, comprobante y estado en web. Las pruebas locales no verifican las credenciales del proveedor en Railway.

Referencia del proveedor: https://developer.paypal.com/api/make-api-requests (idempotencia) y https://developer.paypal.com/api/rest/integration/orders-api (aprobación y captura).


## Modalidad y columna de pago en citas

Después de aceptar una cita, el cliente elige Wallet, Online o Presencial. La misma ruta de pago recibe method=WALLET/ONLINE/PRESENCIAL. Online crea o reanuda la orden PayPal y devuelve approval_url; solo la captura verificada marca el pago como completado. Wallet descuenta USD 5 y completa el cobro en una transacción. Presencial queda pendiente hasta el cobro en caja. Una orden PayPal iniciada debe verificarse antes de cambiar de modalidad.

La API de citas devuelve payment_status (PAID, UNPAID o UNRECORDED), payment_preference (ONLINE o PRESENCIAL), payment_method y payment_id. Estos datos se obtienen del cobro vinculado, no del estado de la cita. Una cita antigua confirmada sin cobro vinculado se muestra como «Sin pago registrado»; no se presume que esté pagada. Gestión de citas muestra la columna Pago y un botón de cobro para consultas aceptadas con pago presencial pendiente; caja conserva el registro del cobro. El historial y las estadísticas de caja se actualizan mediante la consulta periódica mientras está abierto ese apartado; solo incluyen cobros de caja web.

Si /openapi.json no incluye /api/v1/wallet y /api/v1/wallet/topups, la versión publicada aún no contiene este módulo. En Railway, Redeploy repite el código de un despliegue anterior. Usar la paleta de comandos, Deploy Latest Commit, para desplegar main desde el repositorio backend correcto. Luego comprobar los Deploy Logs, el paso python prepare_db.py y las rutas publicadas. Referencia: https://docs.railway.com/deployments/deployment-actions.

## Configuración local y comprobación de PostgreSQL

`run_local.py` carga `.env.local`; añadir allí `PAYPAL_CLIENT_ID` y `PAYPAL_CLIENT_SECRET` de la misma app Sandbox, junto con `PAYPAL_BASE_URL=https://api-m.sandbox.paypal.com`. Para iniciar con `run.py`, se carga `.env`. Los valores `your-paypal-sandbox-client-id` y `your-paypal-sandbox-secret-key` son ejemplos y producen `401 invalid_client`. En Railway configurar esas variables del servicio backend. Nunca incluir secretos en Git ni en el cliente móvil/web.

Los bloqueos de consulta, pago y saldo indican explícitamente la tabla (`FOR UPDATE OF payments`, etc.). Esto evita bloquear el lado nullable de los LEFT JOIN de cashier/tenant en PostgreSQL. Las pruebas SQLite no reproducen ese error; la prueba de regresión compila las consultas reales de los endpoints con el dialecto PostgreSQL y verifica la tabla bloqueada. El manejador de errores conserva los detalles SQL en los logs y devuelve un mensaje comprensible a la app.

## Separación de caja y mobile

- Caja web: `purpose=POS` o consulta con `cashier_id` asignado. El cajero define los importes de sus cobros POS y elige efectivo o PayPal.
- Mobile: consulta online/wallet sin cajero y `WALLET_TOPUP`. Suscripciones Premium personales se guardan en `subscriptions` y sus recibos personales. Cada checkout mobile es USD 5, calculado/validado por backend.
- Elegir presencial solo notifica y conserva pendiente la cita; la consulta entra en caja cuando el cajero inicia su cobro. El historial mobile excluye registros de caja. La API de captura y comprobantes aplica el mismo alcance.
- Mobile abre la URL de aprobación de PayPal en una aplicación externa (navegador). El comprador inicia sesión con su cuenta **Personal Sandbox**, revisa USD 5 y decide aprobar. La cuenta Business recibe los fondos; no se usa como comprador. Abrir el enlace o volver desde PayPal no acredita saldo ni activa Premium: hace falta verificar/capturar el pago.
- Las credenciales se configuran exclusivamente en variables del backend. Los archivos locales de entorno están ignorados por Git; Railway necesita sus propias variables actualizadas y el backend redesplegado.

## Separación de pantallas y cancelación de selección

- Perfil > Wallet permite recargar USD 5, consultar movimientos y recibos de recargas y pagos realizados con wallet. El botón se llama «Recargar wallet USD 5 con PayPal».
- El pago de una cita muestra solo el saldo de wallet y los pagos/comprobantes de esa cita; no muestra controles de recarga, movimientos generales ni recargas pendientes de Perfil.
- Antes de descontar wallet, un diálogo permite confirmar o cancelar. El pago completado muestra un recibo breve con concepto, importe, método, fecha y referencia; el PDF sigue disponible.
- «Cancelar selección y volver a elegir» restablece un pago pendiente a PENDING. Solo el dueño de la cita puede hacerlo; un pago completado o en caja no se cambia. Para una orden PayPal primero se consulta al proveedor: si está aprobada/completada se verifica y completa la operación original; si aún no fue aprobada, se retira la referencia local y se permite otro método. La orden vieja no puede capturarse por las rutas de la app y el siguiente checkout usa otra clave de idempotencia. No es un reembolso ni una cancelación de la cita.
- Las notificaciones de recarga, pago de cita y suscripción Premium se guardan junto a la operación. El envío FCM se encola después del commit; los fallos de push no revierten pagos.

Para activar Firebase y probar avisos con Android cerrado sigue **mobile/docs/NOTIFICACIONES_PUSH.md** en el repositorio raíz del proyecto.
