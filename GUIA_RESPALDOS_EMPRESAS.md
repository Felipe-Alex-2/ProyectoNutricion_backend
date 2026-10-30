# Empresas, sucursales y recuperación operativa

Implementación del 29 de octubre de 2026.

## Activación

Con PostgreSQL disponible y las variables del entorno configuradas, ejecutar desde `backend`:

```powershell
.\.venv\Scripts\python.exe prepare_db.py
```

La migración `20261029_03` crea sucursales, asociaciones de administrador y reportes guardados; agrega empresa a la bitácora y fecha de atención a las citas. Las cuentas globales anteriores `ADMIN_SAAS` pasan a `SUPERADMIN` y deben iniciar sesión nuevamente. Los administradores de empresa conservan `ADMIN_ORGANIZATION`. Cada empresa existente recibe su sucursal principal. No se promueve ninguna cuenta de paciente.

Se eliminan los eventos históricos de navegación/acceso definidos por la migración y se vacían todas las IP de la bitácora. La columna antigua se conserva por compatibilidad, pero no se expone ni se respalda y las nuevas operaciones no guardan IP.

El PostgreSQL configurado localmente no respondió durante la implementación. Se verificó esta migración sobre bases SQLite temporales; no se modificó la base configurada.

## Crear una empresa

1. Iniciar sesión como superadmin y abrir Administración → Empresas.
2. Elegir una cuenta activa de Administrador disponible. Si hace falta, preparar una cuenta desde esa pantalla con nombre, correo y contraseña fuerte.
3. Indicar nombre/código de empresa y primera sucursal. Se asigna ese administrador y se invalida su sesión anterior para que ingrese con el ámbito nuevo.
4. Agregar más sucursales desde Empresas o desde Administración → Sucursales.
5. Los registros web y móvil muestran empresas activas y las sucursales de la empresa seleccionada. El registro público siempre crea pacientes.

El superadmin gestiona la plataforma; el administrador de empresa gestiona exclusivamente su propia empresa. Las sucursales pertenecen a una empresa; el aislamiento de operaciones se realiza por empresa, no por sucursal.

## Contenido del respaldo

- Cobros `COMPLETED` de la empresa (efectivo/PayPal).
- Planes nutricionales, recetas y asignaciones.
- Citas `COMPLETED`, marcadas expresamente como atendidas después de su fecha. Confirmar no equivale a atender.
- Bitácora de operaciones de esa empresa, sin navegación ni IP.
- Reportes guardados. Guardar reporte o exportar PDF/Excel conserva una instantánea del resultado en la empresa.

No incluye usuarios, contraseñas, roles, tokens, chats, expedientes clínicos ni suscripciones. Por ello recupera operaciones de una empresa existente; no reemplaza un respaldo completo de infraestructura. Si falta un paciente u otra relación imprescindible, se informa como omitido y no se inventa una cuenta.

Los reportes PDF/Excel descargados antes de esta versión no pueden recuperarse retroactivamente: no existían como registros persistidos.

## Recuperación

1. En Copias de seguridad seleccionar empresa (obligatorio para superadmin).
2. Generar/descargar el archivo cifrado o cargar un archivo operativo versión 2.
3. La revisión no escribe datos: muestra faltantes, existentes y omitidos por categoría, con motivos de las relaciones faltantes.
4. Confirmar con la contraseña de la cuenta actual. La revisión tiene validez de 15 minutos y está ligada a cuenta, empresa, archivo y estado revisado.
5. Solo se insertan faltantes en una transacción. No se actualizan ni borran los existentes. Se verifican claves primarias, restricciones únicas y referencias de pago; las asignaciones de recetas también se comparan por receta y paciente.
6. Si cambian el archivo o los datos entre revisión y confirmación, analizar de nuevo. Volver a cargar un respaldo ya recuperado muestra cero faltantes.

Solo superadmin o administrador de empresa pueden recuperar. Un archivo de otra empresa se rechaza. El archivo requiere la misma `BACKUP_ENCRYPTION_KEY` con que se creó; conservar esa variable fuera del repositorio. No confundir esa clave técnica con la contraseña que se pide al usuario para confirmar.

Los respaldos anteriores versión 1 no se importan mediante este flujo porque incluían otras tablas y tenían semántica de actualización. Generar un nuevo respaldo operativo versión 2.

Las configuraciones automáticas ahora son por empresa. El programador debe ejecutar `python run_backups.py`; se omiten las configuraciones globales antiguas. La programación del sistema operativo/hosting depende del despliegue.

## Verificación

Las pruebas cubren aislamiento, creación/asignación de empresa, registro con sucursal, revisión sin escritura, contraseña errónea, revisión desactualizada, recuperación parcial y repetida, claves de negocio repetidas y relaciones faltantes, reportes guardados, citas atendidas y bitácora sin IP/navegación.
