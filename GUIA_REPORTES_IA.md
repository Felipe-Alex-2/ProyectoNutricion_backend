# Reportes por texto y voz: empresas y sucursales

## Qué se puede solicitar

El asistente transforma lenguaje natural en un plan de consulta validado. Gemini interpreta las peticiones cuando está configurado `GEMINI_API_KEY`; si la API no está disponible se utiliza interpretación local para las solicitudes habituales. Los resultados se calculan mediante SQLAlchemy sobre datos reales. La IA no ejecuta SQL libre ni decide los permisos.

Ejemplos:

- «¿Qué empresa tiene más clientes?» (superadmin).
- «¿Qué sucursal tiene más clientes activos este mes?».
- «Compara los clientes de Nutri Norte y Vida Sur» (superadmin).
- «Clientes de sucursal Terminal de empresa Nutri Norte».
- «Ingresos cobrados por sucursal este mes en USD».
- «Cantidad de cobros por método de pago».
- «Pacientes únicos atendidos por mes este año».
- «Cantidad de citas canceladas el mes pasado».
- «Tasa de cancelación de citas por sucursal este año».
- «Cobros mayores a 100 USD».
- «Promedio de calorías de recetas por empresa».
- «Planes nutricionales aprobados por especialista».

Fuentes: pacientes, citas, cobros, recetas, fichas clínicas, planes nutricionales y bitácora. Agrupaciones: empresa, sucursal, mes, estado, especialista y método de pago, según el tipo de dato. Métricas: cantidad, suma, promedio, pacientes únicos y tasa de cancelación de citas. Los filtros estructurados permiten igualdad, desigualdad, rangos, listas y búsquedas en campos autorizados.

No se garantiza interpretar cualquier frase imaginable. Cuando no existen la fuente, métrica o filtros necesarios, se solicita una petición más concreta en lugar de sustituirla silenciosamente por otro reporte. No hay predicción de ingresos ni rentabilidad sin los modelos/datos correspondientes.

## Alcance y significado

- Superadmin: una, varias o todas las empresas y sucursales autorizadas.
- Administrador: sucursales de su empresa; no puede solicitar datos de otra empresa por voz ni enviando IDs manualmente.
- Nutricionista: empresa propia y sus pacientes vinculados/citas/fichas/planes propios.
- Cliente: no tiene acceso a reportes internos.
- Cliente/paciente significa cuenta con rol `CLIENTE`. No cuenta al equipo. «Activos» o «inactivos» se aplica solo cuando se solicita.
- Clientes «este mes» significa registrados en ese mes. Pacientes «atendidos» se calculan sobre citas `COMPLETED` en sus fechas; un paciente con varias citas cuenta una vez si se pide pacientes únicos.
- Los cobros de ingresos usan `COMPLETED` y fecha de cobro (o fecha de creación si no consta pago). USD, BOB y otras monedas no se suman entre sí ni se presentan como un solo ranking monetario.
- Las fechas de consulta y agrupaciones mensuales usan Bolivia, UTC−4. «Este mes» termina en el día actual; «mes pasado» es el mes calendario anterior.
- Se ordenan/calculan los grupos sobre todos los registros autorizados antes de limitar las filas presentadas. Se incluyen empresas/sucursales vacías en conteos y se indican los empates.
- Los registros sin sucursal aparecen en un grupo separado. No se inventa una atribución.

## Interfaz y exportación

En Reportes puedes escribir o dictar la petición, seleccionar múltiples empresas/sucursales, cambiar agrupación y métrica, consultar conclusión, gráfica y tabla, guardar y exportar Excel/PDF. El plan interpretado se conserva en vista previa, guardado y ambas exportaciones; los archivos incluyen criterios y conclusión. Los filtros más específicos interpretados por IA se conservan al exportar.

Se descartan respuestas tardías cuando se abandona la pantalla o llega una consulta más nueva.

Los reportes guardados de una sola empresa entran en su respaldo operativo. Los reportes que comparan varias empresas se guardan a nivel plataforma y son exclusivos del superadmin; no se incluyen en el respaldo privado de una empresa porque contienen datos de varias.

## Migración y sucursal histórica

Ejecutar `python prepare_db.py` desde backend cuando PostgreSQL esté disponible. La revisión `20261029_04` agrega `branch_id` a cobros y citas y permite guardar reportes globales. En datos históricos solo asigna sucursal automáticamente cuando la empresa tiene exactamente una. Si tiene varias, conserva sin asignar. Los cobros/citas nuevos guardan la sucursal de la operación y no cambian al trasladar una cuenta.

Para recetas, fichas y planes, la sucursal se deriva de la cuenta asociada; la nota del reporte lo indica. Su empresa siempre se filtra por la empresa guardada en el registro.

La base local configurada no respondió durante esta implementación. Migraciones y consultas se probaron sobre bases temporales; falta activar PostgreSQL local para comprobar con datos reales. No se expusieron claves ni se enviaron datos clínicos al intérprete: su contexto contiene estructura de reportes y nombres de empresas/sucursales autorizadas.

Se realizó además una llamada real a Gemini con una base temporal y datos ficticios: interpretó la comparación por sucursal y el motor devolvió Demo Centro = 2 y Demo Sur = 1. No se usaron datos de pacientes reales en esa comprobación.
