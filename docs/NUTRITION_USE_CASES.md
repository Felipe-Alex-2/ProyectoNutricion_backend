# CU-13 a CU-18: planes y diario nutricional

- CU-13: nutricionista vinculado o administrador autorizado genera un borrador con Gemini, revisa y aprueba. Aprobar asigna el plan, archiva el anterior y notifica al paciente. Sin clave o respuesta válida no se inventa un resultado de IA.
- CU-14: `GET /api/v1/plans/my-plan` devuelve solamente el plan aprobado de la cuenta autenticada. Los borradores no se publican al paciente.
- CU-15: `POST /api/v1/food/analyze` admite JPG, PNG, WebP y HEIC (máximo 10 MB). El paciente registra su propia comida. El profesional puede indicar `patient_id` en multipart, sujeto a clínica y vínculo.
- CU-16: la app móvil descarga el plan y el historial nutricional, y los conserva por cuenta durante 30 días. Identifica la consulta sin conexión y la guía local; no promete IA generativa offline.
- CU-17: el paciente registra comida, fecha/hora y nutrientes opcionales sin internet. La app conserva primero el registro en almacenamiento seguro.
- CU-18: la cola sincroniza con la sesión activa al recuperar conexión, mediante reintentos con espera creciente y un botón de reintento. Cerrar sesión no borra comidas pendientes. Las restricciones del sistema operativo impiden prometer sincronización con la app completamente cerrada.

## API de registro manual

`POST /api/v1/food/records` recibe `client_record_id` (UUID), `description` (1–500 caracteres), `meal_type`, `consumed_at` (ISO 8601 con zona horaria), `calories` (0–10000), `protein_g`, `carbs_g` y `fats_g` (0–1000). Los nutrientes son declarados por el usuario, no una estimación de IA.

El propietario se obtiene del JWT. La combinación cuenta/UUID determina el identificador persistido. Un reintento idéntico devuelve el registro existente; reutilizar el UUID con otros datos responde 409. El historial puede consultarse con `patient_id` únicamente cuando las políticas de acceso lo permiten. Se conserva la fecha real de consumo en `details.consumed_at` y la de recepción en `created_at`.

Se reutiliza la tabla `food_records` y su JSON; esta entrega no requiere una migración de esquema.

## Configuración y despliegue

En Railway, abrir el **servicio backend → Variables** y configurar `GEMINI_API_KEY` si aún no existe. `GEMINI_MODEL` selecciona el modelo. No colocar claves en Angular, Flutter, GitHub, capturas ni archivos versionados. No es necesaria una clave de Groq para esta integración.

`.gitignore` excluye `.env` y sus variantes; `.railwayignore` evita enviarlos en despliegues desde CLI. Railway recibe la clave mediante Variables, no desde el repositorio. Las credenciales que ya se hubieran publicado anteriormente requieren rotación independiente.

Antes de publicar la web, verificar su URL de API de producción: debe ser el dominio público HTTPS real del backend con `/api/v1`, nunca localhost. En GitHub, la compilación móvil requiere la variable de repositorio pública `API_BASE_URL` con esa URL; no contiene secretos.

Validación: `python -m pytest tests -q`; en web `npm test -- --watch=false` y `npm run build`; en móvil `flutter analyze` y `flutter test`.
