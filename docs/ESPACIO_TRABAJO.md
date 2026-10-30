# Empresa y sucursal activas

Las cuentas mantienen su empresa/sucursal de pertenencia (`tenant_id`, `branch_id`). La selección de trabajo se guarda por separado (`workspace_tenant_id`, `workspace_branch_id`) y no traslada usuarios, pacientes ni datos históricos.

- Superadmin: vista global, una empresa con todas sus sucursales, o una sucursal concreta. La vista global conserva reportes comparativos.
- Administrador y nutricionista: su empresa fija y una sucursal activa de esa empresa. No pueden solicitar una vista global ni enviar una empresa ajena.
- Cliente: conserva la empresa/sucursal de registro. No recibe controles ni permisos para cambiar de espacio.

## API y almacenamiento

`GET /api/v1/users/me/workspace-options` ofrece únicamente las empresas/sucursales activas autorizadas. `PUT /api/v1/users/me/workspace` valida la selección y la recuerda para próximos accesos. El login devuelve el espacio recordado; la web pide confirmarlo después de autenticar al personal.

Cada solicitud de la web lleva `X-Workspace-Company` y `X-Workspace-Branch`. Se validan contra los permisos reales del usuario; `all` solo amplía alcance para superadmin. Capturar estos valores por solicitud evita que una respuesta/reintento anterior salte a otra sucursal. Las aplicaciones que no envían cabeceras utilizan el espacio recordado del usuario.

La política central de SQLAlchemy filtra consultas ORM y operaciones masivas de los registros operativos. También valida y atribuye escrituras: pacientes/equipo, recetas y asignaciones, fichas clínicas, anamnesis, planes IA, alimentación/fotos, chat, citas, cobros, suscripciones/comprobantes, notificaciones, bitácora, reportes guardados y respaldos. Los accesos directos a pacientes/planes/reportes usan consultas sometidas al mismo límite.

Los catálogos compartidos (geografía, roles/permisos, alimentos y reglas del sistema experto), la autenticación y las definiciones de empresas/sucursales mantienen sus políticas específicas. No son operaciones clínicas de una sucursal. Crear empresas y administrar la plataforma sigue limitado al superadmin; crear/editar sucursales sigue limitado a administradores de la empresa correspondiente.

La sucursal de una operación guardada no se cambia al cambiar de perfil. El reporte usa la sucursal histórica del registro, no la sucursal actual de su creador. Un nuevo cobro exige la sucursal activa. Crear usuarios del equipo incluye sucursal de pertenencia. Registros de pacientes generados desde callbacks/tareas se atribuyen por su dueño, sin un contexto global mutable de proceso.

Los respaldos por sucursal contienen su identificador y solo registros de esa sucursal. La revisión de restauración está ligada al usuario, empresa, sucursal, archivo y estado de datos. Un respaldo completo de empresa o antiguo sin sucursal se recupera desde la vista de empresa/global del superadmin; no se mezcla con una restauración de sucursal. Los respaldos no recuperan cuentas ni credenciales.

## Actualización

1. Desplegar backend y ejecutar `python prepare_db.py` (migraciones `20261030_05` de geografía y `20261030_06` de contexto).
2. Desplegar frontend. El cambio de espacio recarga el dashboard para eliminar estado y respuestas pendientes de la selección anterior.
3. Confirmar espacio al iniciar sesión; también se puede cambiar desde Perfil o los selectores compactos de los módulos.

La migración conserva datos existentes. Rellena sucursal solamente cuando se puede determinar desde el paciente/dueño o cuando la empresa tiene exactamente una sucursal. Los registros antiguos cuya sucursal no se puede determinar quedan sin atribución y se consultan desde la vista de empresa/global del superadmin. No se asignan a una sucursal arbitraria.

Las pruebas usan datos ficticios y bases temporales. No se han ejecutado estas migraciones en el PostgreSQL de Railway desde esta sesión.
