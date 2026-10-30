# Despliegue del backend en Railway

El error `Production requires a unique SECRET_KEY of at least 32 characters` significa que `ENVIRONMENT` está en producción pero `SECRET_KEY` falta, es corta o conserva una clave de ejemplo. No es un fallo de las vistas ni del menú.

## Variables del servicio backend

En Railway, abrir el servicio de la API y la pestaña Variables. Usar `.env.railway.example` como referencia; sus marcadores deben sustituirse.

- `ENVIRONMENT`: `production`.
- `SECRET_KEY`: una clave privada aleatoria de al menos 32 caracteres, sin prefijos de ejemplo `supersecret` o `change-this`.
- `BACKUP_ENCRYPTION_KEY`: otra clave aleatoria independiente de al menos 32 caracteres. Si ya hay respaldos cifrados en uso, conservar su clave existente; reemplazarla impide leer esos archivos con la clave nueva.
- `DATABASE_URL`: referencia a PostgreSQL en Railway, por ejemplo `${{Postgres.DATABASE_URL}}`. Cambiar `Postgres` por el nombre real del servicio. No usar localhost.
- `FRONTEND_URL`: URL HTTPS real del frontend.
- `CORS_ORIGINS`: el origen HTTPS real del frontend, sin barra final. Se pueden indicar varios separados por comas. No incluir localhost en producción.

Generar cada clave en una terminal local ejecutando dos veces:

```powershell
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Pegar los valores únicamente en Variables de Railway. No enviarlos por chat ni guardarlos en Git. Mantenerlos estables entre despliegues. Cambiar `SECRET_KEY` invalida las sesiones anteriores.

## Comandos

La carpeta raíz del servicio debe ser la que contiene `run.py`, `requirements.txt`, `railway.toml` y `prepare_db.py`. En un despliegue del repositorio padre corresponde a `/backend`; si el repositorio conectado ya es el backend, corresponde a `/`.

La configuración `railway.toml` ya define:

- Predeploy: `python prepare_db.py`, para aplicar las migraciones pendientes.
- Start: `python run.py`, que escucha en `0.0.0.0` y usa el `PORT` proporcionado por Railway.
- Healthcheck: `/health`.

Aplicar los cambios pendientes de Variables y desplegar. Revisar que termine correctamente el predeploy y que `/health` devuelva HTTP 200. Si la configuración falla primero por SECRET_KEY, todavía no ha comprobado las demás variables; corregir también la clave de respaldos y CORS para evitar el siguiente fallo.

Para conservar los archivos de respaldo entre despliegues, montar un volumen persistente en `/data` y configurar `BACKUP_DIR=/data/backups`. El volumen almacena archivos; las migraciones preparan PostgreSQL.

Documentación oficial: https://docs.railway.com/variables
