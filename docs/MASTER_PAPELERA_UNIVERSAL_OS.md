# PAPELERA UNIVERSAL OS — DOCUMENTO MAESTRO
**Versión:** 1.0 · **Fecha:** 5 de noviembre de 2026 · **Estado:** especificación inicial para desarrollo y validación operativa

> **Principio:** la planilla `Libro2.xlsx` es la fuente vigente de Papelera Universal, según confirmación expresa del titular. La lista `lista-de-precios 22 10 (1).xlsx` corresponde a Del Mar, con fecha de vigencia indicada 12/10/2026. No alterar datos originales en las importaciones.

## 1. Visión y objetivos
Construir un sistema de gestión de escritorio para Papelera Universal, orientado a la operación diaria de una papelera minorista, comercial y mayorista argentina. Debe funcionar localmente sin conexión permanente a internet, sin alojamiento web, dominio ni suscripción obligatoria. Debe administrar productos, variantes y presentaciones; listas de precios por segmento y cantidad; múltiples proveedores y listas de costo; compras; inventario; ventas; caja; clientes; comprobantes internos; y, posteriormente, facturación electrónica fiscal e integración entre sucursales y e-commerce.

**Objetivos del MVP:** (a) cargar fielmente la base actual; (b) importar y comparar listas de proveedores, con aprobación humana; (c) calcular precios por reglas configurables sin perder excepciones; (d) registrar compras, stock y ventas de mostrador con trazabilidad; (e) respaldar y restaurar datos; (f) empaquetar una aplicación de escritorio usable.

**No objetivos del MVP de 2 días:** facturación fiscal productiva, e-commerce, sincronización real de múltiples sucursales, contabilidad completa, IA generativa, integración con pasarelas de pago, gestión compleja de promociones omnicanal. Diseñar interfaces y contratos para futuras fases, no simulaciones que aparenten estar activas.

## 2. Fuentes de datos examinadas
### 2.1 Papelera Universal (`Libro2.xlsx`)
- Hoja: `Univ. Papel.`; encabezados en fila 2; columna B `CODIGO`, C `Producto`, D `Pcio Compra Ud`, E `Margen %`, F `Pcio Venta Ud`, G `Precio 3 Uds`, H `Precio 5 Uds`, I `Precio 50 Uds`, J `Precio Gastro`, K `Stock Inicial Uds`, L `Compras Uds`, M `Ventas Uds`, N `Stock Final Uds`, O `Utilidad`, P `Stock Inicial $$$`, Q `Compras $$$`, R `Ventas $$$`, S `Stock Final $$$`.
- Algunas columnas más allá de S pueden estar reservadas o formateadas. Determinar el último registro válido por código + descripción, no por dimensión del formato.
- La celda C1 dice `BALANCE 24 DE OCTUBRE 2016`, pero el usuario **confirmó que el documento completo está actualizado**. No invalidar ni reemplazar sus datos por la fecha del encabezado.
- Ejemplos verificados: código 15057 `ARRANQUE CHICO`, costo 2175, campo `Margen %` 2.1 y precio unitario 4567.5; código 567 `AGITADORES CAFE BLANCOS X 100 UD`, costo 310, campo 3.2 y precio unitario 1000. Esto confirma que el campo E NO puede interpretarse automáticamente como porcentaje convencional: para varios registros es un **factor multiplicador**, y existen precios editados/ajustados manualmente.
- Conservar todos los importes actuales, aun si no coinciden exactamente con el factor. Registrar observaciones y diferencias sin modificar datos en carga inicial.
- Algunas filas contienen costo cero o códigos alfanuméricos; son válidas para importar como borrador/bloqueadas para recálculo, no para eliminar silenciosamente.
- Las columnas K a S son un **snapshot comercial/contable**. El stock final N sirve como saldo inicial de apertura del nuevo sistema. NO volver a reproducir compras y ventas históricos de L/M como transacciones nuevas (produciría doble conteo).

### 2.2 Proveedor Del Mar (`lista-de-precios 22 10 (1).xlsx`)
- Exportado desde Numbers con hoja informativa `Resumen de exportación` y hojas `Hoja1` a `Hoja4`. La hoja `Hoja1` muestra encabezados de categoría repetidos, `CODIGO`, descripción, `P. x menor`, `P x mayor`; en su fila 19 aparece `LISTA DE PRECIOS VIGENTE AL 12/10/2026`.
- No asumir que todo el libro es una sola tabla de encabezado fijo: detectar secciones, rótulos, filas vacías y encabezados por hoja. Registrar origen (hoja, fila, categoría, versión de importación).
- Los precios son denominados **precios finales** en el documento; verificar condiciones tributarias de cada proveedor antes de inferir IVA neto o costos comparables. Guardar por separado precios minoristas y mayoristas, y su condición mínima de compra si se conoce.
- La coincidencia de códigos entre Del Mar y Papelera Universal **no está garantizada**. Debe existir tabla explícita de equivalencias y opción de revisión manual.

### 2.3 Integridad de migración
Generar una bitácora de importación con filas totales, válidas, incompletas, repetidas, omitidas y advertencias. Guardar archivo original y su hash SHA-256. Informar errores, no corregir los orígenes automáticamente. El usuario debe aprobar un resumen antes de activar la base. Exportar reporte CSV de incidencias y verificación de conteos/sumas.

## 3. Decisiones de arquitectura
- **Plataforma inicial:** Windows 10/11 x64. Si el equipamiento concreto exige macOS, evaluar el instalador correspondiente, sin bloquear la estructura de código.
- **Aplicación:** Tauri 2 + React + TypeScript. Interfaz local empaquetada; sin servidor remoto en el MVP.
- **Base de datos:** SQLite local en directorio de datos de aplicación, con migraciones versionadas, claves foráneas habilitadas y transacciones ACID. Usar DECIMAL representado por unidades enteras de precisión fija para dinero y cantidades donde aplique, evitando errores de flotantes; en SQLite preferir enteros de centavos/unidades mínimas o librería decimal y validación estricta.
- **Motor de negocio:** comandos de dominio localizados del lado Rust/Tauri o servicio de aplicación controlado, nunca en componentes de UI. No permitir que vistas escriban directamente tablas de negocio.
- **Offline-first:** venta, stock, compras, búsqueda, precios y tickets internos funcionan sin internet. Acceso a red solo en integraciones explícitas.
- **Extensibilidad:** UUID/ULID globales, `branch_id`, `created_at`, `updated_at`, número de versión por entidad, registros de auditoría y `external_id`. No implementar aún sincronización; diseñar contrato futuro y políticas de conflictos.
- **Sin recurrencias forzadas:** sin hosting ni dominio para funcionamiento local. Puede haber costos por equipos, soporte, impresoras, backups o servicios de terceros.
- **Repositorios:** un repositorio Git con carpetas `src/`, `src-tauri/`, `docs/`, `tests/`, `fixtures/` (datos sintéticos), `scripts/`; mantener los Excel reales fuera de Git público.
- **Seguridad:** contraseñas cifradas con algoritmo de derivación moderno; autenticación local, permisos por rol, secretos fiscales en almacenamiento seguro del sistema operativo; bitácora inmutable a nivel de aplicación. No colocar credenciales en Git ni en frontend.

## 4. Modelo de datos mínimo
Tablas propuestas; nombres refinables durante implementación:
- `products(id, internal_code, name, description, category_id, barcode, base_unit_id, active, created_at, updated_at, version)`; código interno único por empresa, pero preservando texto con ceros iniciales y alfanuméricos.
- `product_presentations(id, product_id, label, units_per_presentation, purchasable, sellable, barcode, active)`. Ej.: unidad, paquete x100, caja x600. Unidades de conversión exactas; no deducir solo del texto sin confirmar.
- `categories`, `units`, `suppliers`, `supplier_products(id, supplier_id, supplier_code, product_id nullable, supplier_presentation_id, conversion_factor, match_status)`.
- `supplier_price_imports(id, supplier_id, filename, file_sha256, source_date, imported_at, status, totals_json)` y `supplier_price_rows(id, import_id, sheet, row_number, supplier_code, raw_name, category, smaller_price, larger_price, parse_status, match_confidence, proposed_product_id)`.
- `supplier_cost_history(id, supplier_product_id, supplier_tier, previous_cost, new_cost, effective_at, import_id, approved_by)`; **no sobrescribir historia**.
- `price_lists(id, name, segment, active)`, `pricing_rules(id, scope_type, scope_id, priority, calculation_type, factor_or_rate, rounding_mode, floor_margin, min_price, manual_override_policy)` y `sale_prices(id, product_id, presentation_id, price_list_id, threshold_qty, currency, amount, effective_at, source, locked, version)`.
- `inventory_balances(branch_id, product_id, base_unit_qty, version)` (lectura), `inventory_movements(id, branch_id, product_id, qty_delta, movement_type, source_id, occurred_at, actor_id)` (libro mayor); stock = suma de movimientos, saldos actualizados transaccionalmente.
- `purchases`, `purchase_lines`, `goods_receipts`, `goods_receipt_lines`, `sales`, `sale_lines`, `payments`, `cash_sessions`, `cash_movements`, `customers`, `branches`, `users`, `roles`, `audit_events`, `settings`, `backup_records`.
- Futuro: `tax_documents`, `tax_authorization_requests`, `sync_outbox`, `sync_inbox`, `device_id`, `external_integrations`, `catalog_publications`.

**Invariantes:** cada venta confirmada y su descuento de stock ocurren en una sola transacción; nunca editar manualmente saldos sin movimiento; compras solo incrementan stock cuando la mercadería es recepcionada; cancelaciones crean contramovimientos, no borran historia; toda modificación de precio registra actor, motivo, fecha, precio anterior y nuevo.

## 5. Precios: política y motor
### 5.1 Interpretaciones matemáticas
- **Factor multiplicador:** precio = costo × factor. Ejemplo: 2175 × 2.1 = 4567.50.
- **Recargo sobre costo (%):** precio = costo × (1 + recargo/100). Ej.: 80% = 1.8×.
- **Margen bruto sobre venta (%):** precio = costo / (1 − margen/100), solo si margen < 100%.
- **Porcentajes de referencia histórico-comercial:** retail 250–500%, comercios 80%, mayorista 40%. **Definir explícitamente** si cada regla es recargo, factor o margen de venta antes de activarla; no aplicar esos porcentajes indiscriminadamente a toda la tabla.
- **Reglas heredadas:** preservar `Margen %` como `legacy_multiplier_or_rule` y precios reales F–J como listas/escalas iniciales. Puede haber precios manuales que no coinciden con el factor.
- **Jerarquía propuesta:** excepción manual de producto/presentación > regla de cliente > regla de segmento/lista > categoría > regla global. Las excepciones requieren fecha y razón; configurables desde Ajustes, no hardcodeadas.
- **Precios por volumen:** columnas `Precio 3 Uds`, `Precio 5 Uds`, `Precio 50 Uds` y `Precio Gastro` se importan como escalas/listas con semántica pendiente de verificación por producto; **no asumir** que son precios unitarios o totales del paquete: deben tener indicador explícito `precio_por_unidad` vs `precio_total_tramo`, validado antes de utilizarse en caja.
- **Redondeo:** a pesos enteros, 10, 50, 100 o umbral configurable por segmento, aplicado al final. Registrar precio sin redondeo para auditoría. Costo cero = no recalcular automáticamente.

### 5.2 Flujo de importación Del Mar
1. Elegir archivo y proveedor; guardar copia y hash.
2. Parsear hojas y detectar secciones, códigos y escalas, emitiendo informe de errores.
3. Normalizar texto solo para búsqueda (mayúsculas, acentos, espacios, `x100`), sin sobrescribir nombre/código original.
4. Vincular mediante mapeos aprobados por identificador de proveedor y código; si no existe, proponer coincidencias de texto, marca, medidas y presentación con **confianza**; nunca aplicar por coincidencia débil automáticamente.
5. Convertir importes a unidades de costo equivalentes mediante factores de presentación aprobados. Mostrar precio menor/mayor y criterios de abastecimiento. No sustituir por el menor costo sin respetar condiciones de compra.
6. Mostrar tabla comparativa: producto, proveedor, costo anterior, nuevo, variación absoluta/%; precio anterior/nuevo por canal; efecto en utilidad; coincidencia y advertencias.
7. Permitir excluir, fijar precio, cambiar regla, aplicar cambio seleccionado o revertir importación mediante nueva operación compensatoria.
8. Confirmación explícita y operación atómica. Conservar toda la trazabilidad. Nueva lista idéntica por hash debe rechazarse o indicarse como reimportación deliberada.
9. Publicar en vistas locales, POS y eventualmente catálogos; jamás reescribir un comprobante histórico.

### 5.3 Casos de protección
Productos sin coincidencia, múltiples coincidencias, costos negativos, moneda distinta, saltos de costo superiores a umbral configurable, presentaciones no equivalentes, precios finales con IVA no homologado, costos cero, productos descontinuados o manualmente bloqueados: **requieren revisión, nunca actualización silenciosa**.

## 6. Inventario y compras
- Stock en unidad base y conversión explícita de presentación. Un paquete de 100 unidades puede venderse como paquete o fraccionado, si está autorizado; reserva y descuento consistentes.
- Movimiento de apertura desde la columna N, con referencia de migración. Columnas K/L/M son información histórica del snapshot, no movimientos nuevos.
- Movimientos: compra recepcionada, venta, devolución, ajuste, merma, transferencia (futuro), reserva/liberación. Registrar usuario, fecha y motivo.
- Stock físico, disponible y reservado; mínimos, punto de pedido, sugerencia de reposición con histórico cuando haya datos suficientes. Configuración por producto.
- Lotes, series y vencimientos solo en categorías que los requieran, no bloquear MVP.
- Compras: pedido a proveedor, recepciones parciales, variaciones de costo, notas internas, egresos y saldos a futuro.
- **Política stock negativo:** bloqueado por defecto; excepción solo bajo permiso especial y registrada.

## 7. POS, clientes y caja
- Búsqueda por código, texto o escáner USB; seleccionar presentación y cantidad; lista de precios visible; descuentos sujetos a permiso; cobros con efectivo/transferencia/tarjeta/mixto.
- Confirmar venta: generar ID, congelar precios e impuestos tal como se cobraron, confirmar pago, debitar stock, registrar movimiento de caja. No producir venta parcial si falla alguna escritura.
- Devolución/anulación con autorización y contramovimiento; reimpresión de comprobantes internos; historial de ventas y apertura/cierre de caja.
- Clientes: consumidor final, comercio, mayorista; listas, condiciones, cuenta corriente y presupuestos; cuentas corrientes pueden tener alcance básico en MVP.
- Comprobante interno: rotulado explícitamente **NO FISCAL**. Nunca presentarlo como factura autorizada.

## 8. Facturación fiscal ARCA — fase posterior
- Integración por web services vigentes según régimen del contribuyente, situación fiscal y tipo de comprobante; revisar documentación y homologación oficial al implementar.
- Requiere conectividad para autorización electrónica; una operación local sin CAE no debe presentarse como factura fiscal validada. Investigar contingencias oficiales aplicables antes de ofrecer emisión offline.
- Manejar certificados, autenticación, punto de venta, tipos de comprobante, numeración, datos del receptor, condición de IVA, importes, impuestos, CAE, vencimiento y QR cuando corresponda. Validar reglas de ARCA vigentes al momento de implementación.
- Separar `sale` (operación comercial), `internal_receipt` (no fiscal) y `tax_document` (autorizado o pendiente), con estados y reintentos idempotentes. Proteger contra comprobantes duplicados.

## 9. Futura arquitectura multisucursal / e-commerce
- MVP: una PC y SQLite; se puede migrar a una base en servidor LAN para varios terminales del mismo local, **no compartir el archivo SQLite sobre una carpeta de red para escrituras simultáneas**.
- Sucursales: un servidor local o una base sincronizada por sucursal y servicio de coordinación; definir si se necesita información en tiempo real vs tolerancia a desconexión. No vender como «sin internet» la sincronización remota; requiere red entre sedes cuando se transmiten cambios.
- Reservas y transferencias de stock deberán tratar conflictos y evitar doble venta. UUID globales, versiones, outbox e idempotencia son prerrequisitos.
- Web/e-commerce futuro: API autenticada y políticas para precios online, stock disponible, pedidos, pagos y protección contra sobreventa. El hosting y dominio se contratarán solo en esa fase si corresponde.

## 10. Interfaz y experiencia
Menú lateral: Inicio; Productos; Precios; Importar Del Mar; Stock; Compras; Ventas; Caja; Clientes; Reportes; Configuración. Diseño sobrio, profesional, rápido, alto contraste, optimizado para operación con teclado y escáner; accesibilidad y mensajes claros. No mezclar valor monetario con factor de margen.

Pantallas MVP prioritarias:
1. **Inicio:** indicadores de stock bajo, ventas de hoy, importaciones pendientes, errores.
2. **Productos:** tabla con código, nombre, stock, costo, precio, listas, proveedor; alta/edición con confirmación.
3. **Importación:** asistente en etapas con vista previa, alertas, vínculos y aprobación.
4. **Precios:** reglas globales/por categoría/producto, comparador y simulador.
5. **Stock:** libro de movimientos, ajuste y recepción.
6. **POS:** búsqueda rápida, carrito, medios de pago, ticket interno.
7. **Seguridad:** backups, restauración, usuarios, auditoría.

## 11. Calidad, pruebas y aceptación
### 11.1 Pruebas automatizadas mínimas
- Calculadora: factor 2.1× con costo 2175 produce 4567.50 antes de redondeo; 80% de recargo = factor 1.8; 40% recargo = 1.4; margen bruto 40% = costo/0.6; margen bruto >=100% inválido.
- Precios manuales: importar precio 1000 con costo 310 y factor 3.2 sin sobrescribir 1000 en la carga inicial.
- Importación: dos ejecuciones del mismo archivo no duplican productos, costos ni movimientos; fila ambigua queda pendiente.
- Stock: compra de 5 y venta de 3 produce +2; venta fallida no descuenta; devolución agrega stock solo al confirmarse.
- Migración: `Stock Final Uds` abre inventario exactamente una vez; no se suman `Compras Uds` y `Ventas Uds` de forma duplicada.
- Caja: venta + pago + movimiento stock atómicos; redondeo monetario exacto; anulaciones reversibles.
- Respaldo: restaurar copia y verificar conteos, saldos, historial e integridad SQLite.
- Permisos: vendedor no puede editar márgenes globales ni ajustar stock sin autorización.

### 11.2 Criterios de salida MVP
- Totales de filas válidas, saldos iniciales y productos importados conciliados con Excel y diferencias documentadas.
- Importador real de Del Mar probado sobre ambos formatos representativos y con al menos una coincidencia manual aprobada.
- No hay cambio masivo de costo/precio sin vista previa y confirmación.
- Flujo completo compra/recepción/venta/ticket/cierre de caja funciona desconectado.
- Se reinicia la PC y persisten todos los datos; backup y restore probados; no aparecen errores críticos en registros.
- Instalador Windows generado y probado en entorno limpio. **Sin estas pruebas: etiquetar ALFA, no producción**.

## 12. Plan concentrado de dos jornadas (estimativo, no garantía)
**Día 1:** crear repo y estructura; migraciones SQLite; importar Excel de Papelera Universal; catálogo editable; mapeos de proveedor; parser Del Mar; cálculo y comparación de reglas; pruebas de importación y precios.

**Día 2:** compras/recepción y libro de stock; POS y caja básica; ticket interno; backup/restauración; permisos iniciales; pruebas integradas y compilación. Si hay bloqueo, priorizar integridad y etiquetar funcionalidades incompletas.

**Prioridad absoluta:** integridad de inventario, preservación de precios históricos, importaciones seguras, ventas transaccionales. **No sacrificar calidad por un plazo de 48 horas.**

## 13. Definición de tareas / backlog
### P0 (indispensable)
- P0-01 scaffolding Tauri/React/SQLite y CI de pruebas.
- P0-02 esquema + migraciones versionadas + seed de categorías/listas.
- P0-03 importación Libro2 con reporte reconciliado, snapshots de inventario.
- P0-04 catálogo y CRUD con validaciones.
- P0-05 parser Del Mar multisección y staging auditado.
- P0-06 equivalencias proveedor-producto y aprobación.
- P0-07 motor de precios y reglas configurables con prioridad.
- P0-08 compras/recepción/ajustes/libro de inventario.
- P0-09 POS transaccional + medios de pago y caja.
- P0-10 tickets internos no fiscales + historial.
- P0-11 copias automáticas y restauración verificada.
- P0-12 pruebas automatizadas, datos sintéticos e instalador.

### P1
- Usuarios/roles granulares, múltiples listas y clientes, presupuestos, devoluciones, etiquetas de productos, lector de código, reportes ABC, stock mínimo, cuentas corrientes, registros de lotes cuando aplique.

### P2
- Integración ARCA homologada, control tributario, impresoras fiscales si corresponden, API futura, múltiples sedes, sync offline, sitio e-commerce, catálogos automáticos, integraciones.

## 14. Reglas de ingeniería para agentes de código
1. Nunca modificar los Excel fuente. No subirlos ni publicar precios reales en el GitHub **público** sin permiso explícito. Usar fixtures sintéticos, tests y `.gitignore`.
2. Trabajar en tareas pequeñas, con commits comprensibles, tests y reporte de cambios. Cada paso debe compilar y no romper módulos anteriores.
3. Toda operación monetaria usa precisión decimal/integer minor units; almacenar moneda (ARS) de forma explícita.
4. No inventar reglas tributarias, factores de conversión, correspondencias de proveedor ni semántica de precios por tramo. Si faltan: registro pendiente y pantalla de decisión.
5. Los saldos de stock derivan de movimientos y se concilian con el snapshot importado.
6. Todas las reglas comerciales se editan en Configuración, prevalencia documentada; no hardcodear políticas.
7. Mantener tablas versionadas y aplicar migraciones reversibles cuando resulte viable; backups antes de migrar datos reales.
8. Toda acción destructiva requiere confirmación y preferencia por soft-delete o ajuste compensatorio.
9. Sin servicios externos obligatorios, sin telemetría ni APIs de terceros sin consentimiento.
10. Mantener README con instalación Windows, comandos, test, backup, restore, limitaciones y pasos para empaquetar.
11. Proteger información real de clientes/proveedores y datos fiscales; nunca dejar credenciales en repositorio.
12. Reportar errores y bloqueos con transparencia, no presentar módulos parcialmente conectados como terminados.

## 15. Decisiones abiertas antes de producción
Estas decisiones no deben impedir programar la base, pero requieren validación antes de activar funcionalidades asociadas:
- Sistema operativo y hardware de la caja real (Windows versión, procesador, impresora, lector).
- Significado exacto por artículo de `Precio 3 Uds`, `Precio 5 Uds`, `Precio 50 Uds`, `Precio Gastro` (precio unitario o total, habilitación y tramo).
- ¿Factor de la columna E es guía u obligación? ¿Se permiten excepciones por artículo? El archivo demuestra excepciones; por defecto **preservar precio efectivo**.
- Identidad fiscal y régimen del contribuyente, punto de venta, serie de comprobantes, categorías IVA y método ARCA. No cargar secretos en documento maestro.
- ¿Inventario de una sola ubicación o varios depósitos desde el inicio? Esquema soporta `branch_id` aunque haya una sola sede inicial.
- Política de redondeo, umbrales de alertas de costo, restricciones de venta bajo costo.
- Si en el futuro se habilitan varias cajas simultáneas: LAN central o sincronización con conflictos.

## 16. Definición de «terminado» y siguiente acción
El documento es una **especificación de implementación**, no prueba de que el programa existe ni garantía de ausencia de defectos. La versión 1.0 fija el alcance y separa hechos comprobados de decisiones a validar. El primer commit de código debería ser el esqueleto instalable, migración SQLite y el importador con pruebas de conciliación, antes de desarrollar pantallas cosméticas.