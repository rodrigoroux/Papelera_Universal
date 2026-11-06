# Papelera Universal OS

**Prototipo local v0.1 — NO listo para producción ni facturación fiscal.**

Aplicación de escritorio offline-first con Python 3.10+, Tkinter y SQLite. Esta implementación valida la operación local; el documento maestro define la evolución hacia una arquitectura extensible, con Tauri/React como alternativa para una versión posterior.

## Iniciar
1. Instalar Python 3.10 o posterior, incluyendo Tkinter.
2. Descargar el código del repositorio (`Code > Download ZIP`).
3. Ejecutar `INICIAR_WINDOWS.bat` (Windows) o `sh INICIAR_MAC.command` (macOS).
4. Importar el archivo **privado** de Papelera Universal desde la interfaz, una sola vez.
5. Importar la lista **privada** de Del Mar para revisión de coincidencias.

También puede ejecutarse desde terminal:

```sh
python papelera_os.py import-universal "ruta/Libro2.xlsx"
python papelera_os.py import-delmar "ruta/lista-de-precios 22 10 (1).xlsx"
python papelera_os.py gui
python -m unittest discover -s tests -v
```

La base local predeterminada se crea en `~/PapeleraUniversalOS/papelera.db`. El repositorio **no incluye** datos comerciales, costos reales ni stock del negocio.

## Implementado
- Catálogo y búsqueda.
- Importación de Excel con detección de duplicados y salvaguarda de apertura.
- Staging de lista Del Mar y candidatos de coincidencia **sin modificar precios**.
- Simulación de precios con factor, recargo sobre costo o margen bruto.
- Ajustes de inventario auditados.
- Venta local con descuento transaccional de stock.
- Comprobante interno marcado **NO FISCAL**.
- Backup SQLite con verificación de integridad.

## Pendiente
Validación manual de homologaciones y unidades; actualización aprobada de precios; reglas por tramo, promociones; compras y recepción; POS y caja completos; usuarios y permisos; restauración asistida; instalador Windows; integración ARCA; sincronización entre sucursales y e-commerce.

## Reglas de protección
- **No subir Excel originales, bases de datos, credenciales ni backups a un repositorio público.**
- El campo `Margen %` histórico puede contener **factores multiplicadores**, no porcentajes.
- Los códigos coincidentes entre proveedor y comercio **no acreditan equivalencia de producto o presentación**.
- Los tickets internos no tienen validez fiscal.
- `Libro2.xlsx` es la fuente vigente según confirmación del propietario; no reinterpretar el stock final como suma adicional de movimientos históricos.
- Las pruebas del repositorio usan datos sintéticos. Antes de uso real se necesitan pruebas adicionales y validación en Windows.

## Documento maestro
[Especificación completa v1.0](docs/MASTER_PAPELERA_UNIVERSAL_OS.md).

## Estado del repositorio
Código fuente del prototipo publicado en `papelera_os.py`, lanzadores y pruebas incluidos. **No existe todavía un instalador .exe** ni una versión certificada para caja.
