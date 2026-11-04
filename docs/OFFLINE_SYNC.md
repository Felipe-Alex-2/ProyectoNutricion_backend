# Reintentos de operaciones sin conexión

Publicar este backend junto con las nuevas versiones web/mobile. No requiere variables de entorno nuevas ni tablas adicionales.

`Idempotency-Key`, opcional (máximo 128 caracteres), identifica una operación del actor autenticado:

- `POST /payments/create`: con identificador solo acepta `EFECTIVO`; devuelve el mismo cobro al reintentar. No se aplica al checkout de PayPal.
- `POST /recipes`: repite la respuesta de la receta original sin duplicarla ni fallar por el mismo título.
- `POST /food/analyze`: conserva la foto analizada y su respuesta; el mismo identificador y bytes no vuelven a llamar a Gemini ni generan otro registro.

Los identificadores UUID se derivan de actor, tipo y clave. Un bloqueo transaccional por actor serializa los reintentos concurrentes en PostgreSQL. Reutilizar una clave con otros datos devuelve 409. Los permisos actuales de empresa, sucursal y acceso al paciente se validan antes de recuperar un resultado anterior. Las citas y los registros alimentarios manuales conservan sus mecanismos de idempotencia existentes.

Los pendientes locales no se consideran cobros confirmados ni se acreditan a wallets. Los comprobantes se generan después de persistir el cobro en el servidor.

Pruebas: `.venv\Scripts\python.exe -m pytest tests/test_offline_replay.py tests/test_nutrition_diary.py tests/test_recipes_and_clinical.py tests/test_consultation_wallet.py -q`.
