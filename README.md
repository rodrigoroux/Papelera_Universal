# Papelera Universal OS

Aplicación local de escritorio para una sucursal, con Python, Tkinter y SQLite. Rama de desarrollo 0.2. Los comprobantes internos se identifican como **NO FISCALES**.

## Inicio

En Windows con Python 3.10+ y Tkinter, ejecutar INICIAR_WINDOWS.bat. En macOS, ejecutar INICIAR_MAC.command con sh. El primer ingreso crea la cuenta administradora. La aplicación almacena los datos en la carpeta PapeleraUniversalOS del perfil del usuario, fuera del directorio de instalación. Las cuentas del programa controlan la interfaz y la CLI. Quien tenga acceso directo al archivo SQLite mediante el sistema operativo también tiene acceso a los datos.

## Operación disponible

1. Importar una única apertura desde el archivo privado de Papelera Universal. Se usa la columna N como saldo inicial. El sistema conserva los precios históricos y señala duplicados y saldos negativos.
2. Cargar Del Mar y buscar una fila. Validar el artículo, la escala y cuántas unidades base contiene la presentación. La propuesta conserva el precio de venta por defecto. Un recálculo requiere elegir fórmula, revisar y aprobar. El umbral de variación es configurable.
3. Crear pedidos de compra por artículo, recibir total o parcialmente, y consultar las cantidades pendientes. Cada recepción incrementa existencias sin sobrescribir el costo aprobado.
4. Abrir caja, elegir productos, armar el carrito y cobrar. Se puede identificar al cliente y combinar efectivo, transferencia y tarjeta. Los importes deben sumar el total. Los movimientos manuales, apertura, arqueo y cierre quedan registrados.
5. El administrador puede anular una venta completa y revertir los pagos en la caja abierta. Los tickets y movimientos originales permanecen consultables.
6. Consultar el historial, existencias críticas y movimientos. Exportar informes a CSV compatible con Excel.
7. Crear respaldos manuales o usar la copia diaria al ingresar. La restauración comprueba esquema, integridad y referencias, conserva una copia previa y obliga a volver a ingresar.

## Instalador de Windows

El flujo de compilación usa un runner Windows estándar únicamente en repositorio público, ejecuta las pruebas, empaqueta Python y Tkinter, instala, abre el programa en modo de diagnóstico y verifica una reinstalación con ventas de prueba. Una ejecución satisfactoria publica el instalador como **prerelease** en Releases. La disponibilidad depende del resultado del flujo. También se puede compilar en una PC Windows x64 con Python 3.12 e Inno Setup 6 mediante packaging/build.ps1. El equipo de caja solo necesita el instalador resultante. El escritorio y el menú Inicio reciben accesos directos. La aplicación y sus datos quedan en carpetas distintas.

## Validación

Ejecutar python -m unittest discover -s tests -v. Las pruebas utilizan datos sintéticos y bases temporales. No incluir Excel reales, copias locales, claves ni bases en Git. El código de la rama principal en 4fbb4e1 conserva la versión anterior.

## Alcance pendiente

Validar instalación y operación en la PC real del local, medios de impresión y significado de los tramos del Excel. La anulación cubre la venta completa. Los precios por presentación/segmento, descuentos, promociones, devoluciones parciales, informes de rentabilidad y la integración fiscal requieren trabajo adicional. La solicitud fiscal local queda pendiente y no solicita ni almacena un CAE.

La próxima integración debe validar con ARCA el régimen fiscal, el punto de venta, los certificados y la autorización WSAA para WSFEv1. Ante una respuesta incierta es necesario consultar el comprobante en el entorno correcto antes de reintentar. Referencias oficiales: https://www.arca.gob.ar/ws/documentacion/ws-factura-electronica.asp y https://www.arca.gob.ar/fe/ayuda/homologacion_externa.asp.

La especificación de alcance está en docs/MASTER_PAPELERA_UNIVERSAL_OS.md.
