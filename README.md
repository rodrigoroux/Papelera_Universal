# Papelera Universal OS

Software de escritorio **offline-first** para Papelera Universal: productos, precios, importación de proveedores, stock, compras, ventas, caja y comprobantes internos.

## Estado
**Etapa de especificación; no existe una aplicación operativa todavía.** El documento maestro completo v1.0 se entregó por separado al propietario el 05/11/2026 y debe incorporarse a `docs/MASTER.md` antes del desarrollo.

## Arquitectura objetivo
- Tauri 2 + React + TypeScript; instalación local Windows.
- SQLite local y migraciones versionadas; sin hosting, dominio o suscripción obligatoria.
- Movimientos de inventario auditables; compras/ventas atómicas.
- Importaciones Excel con staging, homologación de códigos y revisión previa.
- Reglas de precios configurables por lista, categoría, producto, tramo y excepción.
- Preparado para API, sucursales y e-commerce en versiones futuras; no son parte del MVP.

## Datos de origen
- `Libro2.xlsx`: fuente vigente de Papelera Universal, confirmada por el propietario.
- `lista-de-precios 22 10 (1).xlsx`: lista Del Mar; vigencia señalada 12/10/2026.
- **NO SUBIR ESTOS EXCEL AL REPOSITORIO PÚBLICO.** Mantenerlos en el equipo del propietario. Utilizar datos sintéticos en tests.
- No interpretar automáticamente la columna `Margen %` como porcentaje: aparecen factores multiplicadores, y los precios efectivos pueden tener excepciones.
- `Stock Final Uds` constituye el saldo de apertura; no reproducir también compras/ventas históricos en el libro de movimientos.
- Verificar el significado de `Precio 3 Uds`, `Precio 5 Uds`, `Precio 50 Uds` y `Precio Gastro` antes de utilizarlos en caja.

## Secuencia P0
1. Scaffold Tauri, React, SQLite, GitHub Actions y pruebas.
2. Importador Libro2, conciliación e informe de errores.
3. Catálogo editable.
4. Parser Del Mar multisección y mapeos aprobados.
5. Motor de costo/precios con simulación y aprobación.
6. Libro mayor de stock, compras y recepciones.
7. POS, caja y ticket **NO FISCAL**.
8. Backups, restauración, pruebas e instalador Windows.

## Política fiscal
La integración ARCA se implementará en una fase posterior con validación normativa y autorización electrónica. Un ticket interno no equivale a factura fiscal.

## Criterios de calidad
Preservar archivos fuente, operaciones monetarias exactas, trazabilidad completa, ausencia de duplicaciones, controles de permiso, pruebas automatizadas y restauración verificada antes de declarar la aplicación lista para uso productivo.

## Límites
La meta de dos jornadas es un MVP experimental y está condicionada a pruebas. La integración ARCA, la sincronización multi-sucursal y el e-commerce están expresamente fuera de ese alcance inicial.
