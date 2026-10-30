# Ubicaciones de Bolivia

Empresa: departamento. Sucursal: provincia y municipio dependientes del departamento de su empresa.
Los códigos son cadenas, conservando ceros iniciales: Chuquisaca `01`, Oropeza `0101`, Sucre `010101`.

El catálogo local se deriva de [Municipios Bolivia 2024, Laboratorio de Tecnologías Sociales](https://github.com/lab-tecnosocial/municipios-bolivia-2024), archivo `municipios_bolivia_2024.csv`, consultado el 30/10/2026, bajo licencia [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).
Contiene las unidades territoriales del nivel municipal del catálogo, incluidos TIOC con su agrupación censal de origen. Es referencial, no determina límites legales.
Se conservaron códigos y nombres; se descartaron geometrías, superficies y capitales, y se agruparon los registros por departamento y provincia. No se requiere consultar al proveedor al usar los formularios.

Backend: `app/data/bolivia_locations.json`. Web: `src/app/core/data/bolivia-locations.ts`.
Al actualizar, regenerar ambos desde la misma versión del CSV: departamento `idep`, provincia `idep + iprov`, municipio `codigo_ine`, nombres `nombre_dep`, `nombre_prov`, `nombre_mun`. Conservar la atribución.

## Producción

Ejecutar `python prepare_db.py` como paso previo al despliegue de Railway. La migración `20261030_05` agrega columnas anulables a empresas y sucursales, sin inferir ubicaciones previas.
Desplegar primero el backend y luego el frontend. La creación nueva requiere la ubicación completa; los campos anulables conservan lectura de datos históricos y el registro móvil existente.
Completar departamento de empresas anteriores desde Editar empresa, y provincia/municipio desde Editar ubicación y datos de cada sucursal.
Cambiar el departamento se rechaza si contradice las ubicaciones de sucursales ya registradas. No se trasladan sucursales entre empresas.
