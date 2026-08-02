# Somfy Protexial / Protexiom / Protexial IO

[Français](README.md) | [English](README.en.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Italiano](README.it.md) | [Nederlands](README.nl.md) | [Português](README.pt.md)

## Acerca de

Esta integración permite que Home Assistant se comunique con una central de alarma Somfy Protexial, Protexiom o Protexial IO.

### Modelos probados

| Modelo | Versión | Estado |
|---|---:|:---:|
| Protexial IO | `2013 (v10_13)` | ✅ |
| Protexiom 5000 | `2013 (v10_3)` | ✅ |
| Protexiom | `2013 (v10_15)` | ✅ |
| Protexial | `2010 (v8_1)` | ✅ |
| Protexiom | `2008` | ✅ |

Esta lista no es exhaustiva. La integración también puede funcionar con otras versiones de centrales Somfy.

### Funciones compatibles

- Control de la alarma mediante las zonas A, B y C
- Control de persianas
- Control de luces
- Lectura del estado general de la central
- Lectura de fallos y estados de los dispositivos Somfy

### Entidades principales

| Entidad | Descripción |
|---|---|
| `alarm_control_panel` | Modos `armed_away`, `armed_home`, `armed_night` y desarmado |
| `cover` | Apertura, cierre y parada de persianas, sin control de posición |
| `light` | Encendido y apagado de luces |
| `binary_sensor` | Batería, movimiento, apertura, sabotaje, radio, GSM, cámara y estados agregados de dispositivos |
| `sensor` | Operador GSM, calidad de la señal GSM y última sincronización |
| `button` | Reinicio de fallos de batería, alarma y enlace de radio |

## Instalación

### Opción A — Instalación mediante HACS (recomendada)

1. Abra **Integraciones** en HACS.
2. Abra el menú **⋮** y después **Repositorios personalizados**.
3. Añada `https://github.com/AuroreVgn/somfy-protexial`.
4. Seleccione la categoría **Integración**.
5. Busque **Somfy Protexial** y descargue la integración.
6. Reinicie Home Assistant.

### Opción B — Instalación manual

1. Descargue el archivo de la última versión disponible.
2. Localice la carpeta que contiene `configuration.yaml`.
3. Cree `custom_components` si no existe.
4. Cree `custom_components/somfy_protexial`.
5. Extraiga los archivos de la integración en esa carpeta.
6. Reinicie Home Assistant.

## Configuración

En Home Assistant, abra:

**Ajustes → Dispositivos y servicios → Añadir integración → Somfy Protexial**

### 1. Dirección de la central

Introduzca la URL local de la interfaz web de la central, por ejemplo:

```text
http://192.168.1.234
```

Incluya el puerto en la URL si la central utiliza uno no estándar.

### 2. Autenticación

Según la generación de la central, el asistente puede solicitar:

- la contraseña de la cuenta de usuario;
- el código correspondiente al desafío de la tarjeta de autenticación;
- en algunas Protexiom antiguas, un paso de administrador seguido de la contraseña de usuario.

### 3. Configuración adicional

Los modos de armado utilizan las zonas configuradas en la central Somfy:

- **Ausente**: zonas A + B + C;
- **Noche**: combinación opcional de zonas;
- **En casa**: combinación opcional de zonas.

Puede definirse un código de armado. Se solicitará al armar o desarmar.

El intervalo de actualización puede configurarse entre 15 segundos y 1 hora. El valor predeterminado es de 60 segundos.

## Información importante

### Compatibilidad

La lista de modelos probados no es exhaustiva. Puede informar del funcionamiento con otra versión en las incidencias del repositorio o en el [hilo de discusión de HACF](https://forum.hacf.fr/t/integration-custom-centrale-somfy-protexial/23589).

El año de la interfaz suele aparecer al final de las páginas de la central. Algunas centrales también exponen su versión en:

```text
http://DIRECCION_DE_LA_CENTRAL/cfg/vers
```

### Uso de la interfaz web original de Somfy

La central suele admitir una sola sesión de usuario simultánea. Desactive o recargue temporalmente la integración antes de utilizar la interfaz web original si se rechaza la conexión.

### Reconfiguración

La integración puede reconfigurarse desde la interfaz de Home Assistant.

## Contribuciones

Las contribuciones, los informes de errores y los comentarios de compatibilidad son bienvenidos. Consulte [CONTRIBUTING.md](CONTRIBUTING.md) antes de proponer cambios.

## Créditos

El código inicial se basa en parte en la plantilla `integration_blueprint` de Ludeeus.

## Licencia

Este proyecto se distribuye bajo la licencia MIT. Consulte [LICENSE](LICENSE).
