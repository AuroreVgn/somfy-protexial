# Somfy Protexial / Protexiom / Protexial IO

[![GitHub Release][releases-shield]][releases]
[![License][license-shield]](LICENSE)

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg?style=flat-square)](https://github.com/hacs/integration)
[![Maintainers](https://img.shields.io/badge/maintainers-@AuroreVgn%20|%20@the8tre-blue.svg?style=flat-square)](#)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support-FF5E5B?style=flat-square&logo=ko-fi&logoColor=white)](https://ko-fi.com/aurorevgn)

![header](assets/header.png)

> [!NOTE]
> 📚 La documentación detallada del proyecto está disponible en la [Wiki](https://github.com/AuroreVgn/somfy-protexial/wiki), actualmente mantenida en francés.

## Otros idiomas

[English](README.en.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Italiano](README.it.md) | [Nederlands](README.nl.md) | [Português](README.pt.md)

## Acerca de

🔀 Esta versión 2.2.x es un **fork actualizado** de la integración original de [the8tre](https://github.com/the8tre).

Los principales objetivos de esta integración son anticiparse a:

- el **apagado de la red 2G**, proporcionando una alternativa fiable sin necesidad de sustituir todo el sistema de alarma, permitiendo recibir alertas de intrusión (u otros eventos) directamente en Home Assistant y en la aplicación móvil mediante notificaciones críticas (es decir, notificaciones que suenan incluso con el teléfono en silencio).
- el [**cierre de los servidores de Somfy Protexial/Protexiom**](https://forum.hacf.fr/t/integration-custom-centrale-somfy-protexial/23589/223) (aunque se espera que el impacto sea muy limitado).

Esta integración proporciona la comunicación con las centrales de alarma Somfy Protexial, Protexiom y Protexial IO.

### Modelos probados

| Modelo | Versión | Estado | Pausa de elementos |
| -------------- | --------------- | ------------------ | ------------------ |
| Protexial IO | `2013 (v10_13)` | :white_check_mark: | :white_check_mark: |
| Protexiom 5000 | `2013 (v10_3)` | :white_check_mark:  |
| Protexial | `2013 (v10_13)` | :white_check_mark:  |
| Protexial | `2013 (v10_14)` | :white_check_mark:  |
| Protexial | `2013 (v10_15)` | :white_check_mark:  |
| Protexial | `2010 (v7_9)` | :white_check_mark:  |
| Protexial | `2010 (v8_1)` | :white_check_mark:  |
| Protexial | `2008` | :white_check_mark:  |

⚠️ Que un modelo no aparezca en esta lista **no significa** que no sea compatible. Simplemente puede que todavía no haya sido probado o comunicado por otros usuarios.

🔎 La integración permite visualizar el estado de la alarma y de todos sus dispositivos.

👉🏻 La integración permite controlar:

- 🚨 la alarma por zonas (A, B y C)
- 🪟 las persianas
- 💡 las luces
- ⏸️ poner en pausa elementos individuales para realizar tareas de mantenimiento (cambio de pilas)
- 🔄 configurar dinámicamente el intervalo de actualización de los datos (ver más abajo)

🔃 La integración también permite restablecer los fallos de alarma, comunicación por radio y batería.

### 🌍 Idiomas de la interfaz de la central

La integración detecta automáticamente el idioma utilizado por la interfaz web de la central de alarma.

Actualmente se admiten las siguientes interfaces Somfy:

| Idioma | Prefijo |
| --- | --- |
| 🇫🇷 Francés | `/fr/` |
| 🇩🇪 Alemán | `/de/` |
| 🇬🇧 Inglés | `/gb/` |
| 🇪🇸 Español | `/sp/` |
| 🇮🇹 Italiano | `/it/` |
| 🇳🇱 Neerlandés | `/nl/` |

El idioma de la interfaz web de la central es independiente del idioma utilizado en Home Assistant.

#### Entidades compatibles

| Entidad | Descripción | Versión |
| ----------------------------------- | ----------------------------------------------------------- |-----------------------------------------------------------|
| `alarm_control_panel.alarme` | Compatible con los modos `armed_away`, `armed_home` y `armed_night` | 1.2.4 |
| `cover.volets` | Abrir, cerrar y detener. No admite control de posición. | 1.2.4 |
| `light.lumieres` | Encendido/apagado (el estado es mantenido por la integración. No es posible detectar si las luces se han encendido o apagado mediante un mando a distancia, un interruptor u otra integración). | 1.2.4 |
| `binary_sensor.batterie` | Estado agregado de las baterías | 1.2.4 |
| `binary_sensor.boitier` | Estado de la central | 1.2.4 |
| `binary_sensor.communication_radio` | Estado de la comunicación por radio | 1.2.4 |
| `binary_sensor.communication_gsm` | Estado de la comunicación GSM | 1.2.4 |
| `binary_sensor.mouvement_detecte` | Estado de detección de movimiento | 1.2.4 |
| `binary_sensor.porte_ou_fenetre` | Estado de puertas y ventanas | 1.2.4 |
| `binary_sensor.camera` | Estado de conexión de la cámara | 1.2.4 |
| `sensor.signal_gsm_5` | Intensidad de la señal GSM (/5) | 1.2.6 |
| `sensor.operateur_gsma` | Operador GSM | 1.2.6 |
| `sensor.alarme_derniere_sync` | Última sincronización con la alarma (el último valor se restaura después de un reinicio) | 2.0.7 |
| `sensor.fecha_y_hora_de_la_central` | Última fecha y hora leídas directamente de la central (el último valor se restaura después de un reinicio) | 2.1.x |
| `sensor.registro_de_eventos` | Los 10 eventos más recientes del registro de la central. El estado corresponde al último evento y el atributo `events` contiene la lista detallada | 2.2.0 |

#### Se crean los siguientes sensores binarios para representar cada dispositivo de la alarma junto con sus atributos:

| Entidad | Descripción – Atributos | Versión |
| ----------------------------------- | -------------------------------------------------------------------------------------------------------- | --------|
| `binary_sensor.do_ouvt_xxx` | Contacto de puerta: batería, comunicación con la central, fallo, sabotaje, abierta/cerrada, pausado | 2.0.0 |
| `binary_sensor.do_vitre_ouvt_xxx` | Contacto de ventana con detección de rotura de cristal: batería, comunicación con la central, fallo, sabotaje, abierta/cerrada, pausado | 2.0.0 |
| `binary_sensor.do_vitre_ouvt_xxx` | Detector acústico de rotura de cristales: batería, comunicación con la central, fallo, sabotaje, abierta/cerrada, pausado | 2.0.0 |
| `binary_sensor.do_gar_xxx` | Contacto de puerta de garaje: batería, comunicación con la central, fallo, sabotaje, abierta/cerrada, pausado | 2.0.0 |
| `binary_sensor.dm_image_mvt_xxx` | Detector de movimiento con captura de imágenes: batería, comunicación con la central, fallo, sabotaje, pausado | 2.0.0 |
| `binary_sensor.dm_mvt_xxx` | Detector de movimiento: batería, comunicación con la central, fallo, sabotaje, pausado | 2.0.0 |
| `binary_sensor.tr_tel_xxx` | Central de alarma: batería, comunicación con la central, fallo, sabotaje, pausado | 2.0.0 |
| `binary_sensor.clavier_clv_xxx` | Teclado: batería, comunicación con la central, fallo, sabotaje, pausado | 2.0.0 |
| `binary_sensor.cl_lcd_clv_xxx` | Teclado LCD: batería, comunicación con la central, fallo, sabotaje, pausado | 2.0.0 |
| `binary_sensor.sir_ext_xxx` | Sirena exterior: batería, comunicación con la central, fallo, sabotaje, pausado | 2.0.0 |
| `binary_sensor.sir_int_xxx` | Sirena interior: batería, comunicación con la central, fallo, sabotaje, pausado | 2.0.0 |
| `binary_sensor.d_fumee_fumee_xxx` | Detector de humo: batería, comunicación con la central, fallo, pausado | 2.0.0 |
| `binary_sensor.tc_multi_tlcmd_xxx` | Mando a distancia multicanal: comunicación con la central, pausado | 2.0.0 |
| `binary_sensor.tc_4_tlcmd_xxx` | Mando a distancia para varias zonas: comunicación con la central, pausado | 2.0.0 |
| `binary_sensor.badge_bdg_axxx` | Llavero RFID: comunicación con la central, pausado | 2.0.0 |

Los atributos pueden consultarse en el menú **"Detalles"**.

<img width="160" height="243" alt="image" src="https://github.com/user-attachments/assets/1fd0de09-5f3e-4dc0-b147-bb55593adf45" />

<img width="526" height="301" alt="image" src="https://github.com/user-attachments/assets/50ad793d-bddc-44b5-915a-b569b7cb5050" />

#### Botones compatibles

| Entidad | Descripción | Versión |
| ----------------------------------- | ----------------------------------------------------------- |-----------------------------------------------------------|
| `button.reinitialiser_defaut_alarme` | Restablecer los fallos de alarma (movimiento, apertura y sabotaje) | 2.0.7 |
| `button.reinitialiser_defaut_liaison_radio` | Restablecer los fallos de comunicación por radio entre la central y los sensores | 2.0.7 |
| `button.reinitialiser_defaut_piles` | Restablecer los fallos de batería | 2.0.7 |
| `button.refresh` | Restablecer los fallos de batería | 2.0.13 |
| `button.leer_fecha_y_hora_de_la_central` | Lee la fecha y la hora almacenadas actualmente en la central | 2.1.x |
| `button.sincronizar_fecha_y_hora` | Sincroniza la fecha y la hora de la central con la fecha y hora locales de Home Assistant | 2.1.x |


#### ⏸️ Pausa / reactivación de elementos (versión 2.1):

Si se configuran las credenciales de **Instalador**, la integración crea un switch `(PAUSA)` para cada elemento compatible en la categoría **Diagnóstico** del dispositivo.

- **ON**: elemento activo
- **OFF**: elemento en pausa

El comando utiliza temporalmente la cuenta **Instalador** y después vuelve a conectar automáticamente la cuenta **Usuario**.
La página *Lista de elementos* del usuario **Instalador** se detecta con un fallback entre `/fr/i_listelmt.htm` y `/i_listelmt.htm` para mejorar la compatibilidad entre generaciones de centrales.

⚠️ Si la URL de tu central es diferente, indícamelo para que pueda actualizar la integración.

Los iconos coinciden con los de los sensores binarios correspondientes.


> Las centrales Somfy solo permiten una sesión a la vez. La integración gestiona automáticamente el cambio temporal de sesión al pausar o reactivar un elemento.

#### 🔄 Intervalo de actualización dinámico (versión 2.1):
El intervalo de actualización de la integración también está disponible como una entidad `number`. Su valor puede modificarse directamente desde la interfaz o mediante una automatización para adaptar dinámicamente la frecuencia de consulta de la central y así [reducir el consumo de sus pilas](https://github.com/AuroreVgn/somfy-protexial/wiki/Optimisation-de-la-dur%C3%A9e-de-vie-des-piles-de-la-Centrale#avec-un-intervalle-de-rafraichissement-variable).

El valor seleccionado se conserva después de recargar la integración o reiniciar Home Assistant.


#### ⚙️ Ajustes generales de la central (versión 2.1):

Si se configuran las credenciales de **Instalador**, la integración también permite leer y modificar varios ajustes generales de la central desde Home Assistant. Las entidades solo se crean si el ajuste correspondiente está disponible en la central.

| Entité | Description | Paramètre Somfy |
| ------ | ----------- | --------------- |
| `number.temporizacion_de_entrada` | Temporización de entrada, de 1 a 60 segundos | `tempoentree` |
| `switch.ding_dong_en_sirena_interior` | Activa o desactiva DING DONG en la sirena interior | `kiela` |
| `switch.pitido_del_transmisor` | Activa o desactiva el pitido del transmisor | `bipontransmiter` |
| `select.nivel_de_pitidos_de_las_sirenas` | Nivel de pitidos: Bajo, Medio o Alto | `biplevel` |
| `select.nivel_de_sonido_de_las_sirenas` | Nivel de sonido de las sirenas: Bajo, Medio o Alto | `sirenlevel` |

Los cambios se realizan mediante la cuenta **Instalador**. Antes de cada escritura, la integración vuelve a leer el formulario de configuración actual de la central y modifica únicamente el ajuste solicitado para conservar el resto de parámetros.

El botón **Leer fecha y hora de la central** lee la hora realmente almacenada en la central y actualiza el sensor dedicado. **Sincronizar fecha y hora** copia la fecha y hora locales de Home Assistant a la central. Estas funciones también utilizan la cuenta **Instalador**.

#### 📜 Registro de eventos (versión 2.2.0):

La integración expone el **registro de eventos** de la central mediante un sensor dedicado. Los **10 eventos más recientes** están disponibles en el atributo `events` con la fecha, la hora, el evento, el elemento relacionado y el código Somfy. El estado del sensor corresponde al último evento.

El registro se lee con la cuenta **Usuario**, en modo de solo lectura, sin utilizar la cuenta Instalador. Se actualiza como máximo una vez cada 5 minutos para limitar las consultas a la central. Si la lectura falla temporalmente, se conservan los últimos eventos conocidos.

## Instalación

### Opción A: Instalación mediante HACS (recomendada)

1. Añada este repositorio de GitHub a HACS.
   - Automáticamente: [![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?category=integration&repository=somfy-protexial&owner=AuroreVgn) <br />
   - Manualmente:
      - HACS → Integraciones → Menú "..." → Repositorios personalizados
      - Repositorio: `https://github.com/AuroreVgn/somfy-protexial`
      - Categoría: `Integración`
3. Descargue la integración.
   - HACS → Integraciones → Somfy Protexial → Descargar
4. Reinicie Home Assistant.

### Opción B: Instalación manual

1. Descargue el archivo de la última versión disponible: [somfy_protexial.zip](https://github.com/AuroreVgn/somfy-protexial/archive/refs/tags/2.2.0.zip)
2. Localice el directorio que contiene el archivo `configuration.yaml` de su instalación de Home Assistant.
3. Si no existe el directorio `custom_components`, créelo.
4. Cree un directorio `somfy_protexial` dentro de `custom_components`.
5. Extraiga el contenido de `somfy_protexial.zip` en el directorio `somfy_protexial`.
6. Reinicie Home Assistant.

## Configuración

- Añada la integración utilizando [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=somfy_protexial) o manualmente.
- Ajustes → Dispositivos y servicios → + Añadir integración → Somfy Protexial

### 1. Dirección de la central de alarma

- Introduzca la URL de la interfaz web local de su central:
  `http://192.168.1.234` o `http://192.168.1.234:9876`

</br>

<img src="assets/welcome.png" width="50%"><img src="assets/login_io.jpeg" width="50%">

### 2. Credenciales del usuario

- Usuario: `"u"` (**mantenga el valor predefinido**)
- Contraseña: Introduzca la contraseña que utiliza habitualmente.
- Código de autenticación: Introduzca el código de la tarjeta de autenticación correspondiente al desafío solicitado.

<img src="assets/step2.png" width="50%">

### 3. Configuración adicional

Los distintos modos de armado utilizan las zonas configuradas en la central Somfy:

- **Modo ausencia** (siempre configurado): zonas A+B+C
- **Modo noche** (opcional): zonas A, B, C, A+B, B+C o A+C
- **Modo presencia** (opcional): zonas A, B, C, A+B, B+C o A+C


**Código de armado/desarmado:** si especificas un código, seguirá siendo siempre obligatorio para desarmar. La opción **Exigir código para armar** permite elegir si también debe introducirse al armar.

**Intervalo de actualización:** de 0 segundos* a 24 horas (86.400 segundos). El valor predeterminado es 60 segundos (no se recomienda utilizar un intervalo menor, ya que la interfaz web de la alarma tiende a volverse inestable).
*El valor `0` desactiva la actualización automática. El botón **Actualizar datos** permite forzar una sincronización manual en cualquier momento.
Este valor puede modificarse dinámicamente posteriormente mediante una entidad `number`.

**Cuenta de Instalador (opcional):** introduce el nombre de usuario (por defecto `i`) y la contraseña del Instalador únicamente si deseas utilizar los switches `(PAUSA)` para pausar o reactivar elementos individualmente. El control normal de la alarma sigue utilizando la cuenta **Usuario**. La cuenta de Instalador también es necesaria para leer y sincronizar la fecha/hora y para los ajustes generales de la central descritos anteriormente.
## Información adicional

### Tarjeta Lovelace para Home Assistant (estado y control)

Se ha desarrollado una [tarjeta Lovelace](https://github.com/developpeurbox/somfy-protexial-card) específicamente para esta integración.

### Tarjeta Mushroom Template (detalles de los dispositivos)

Hay disponible una plantilla de Home Assistant para mostrar cada dispositivo de la alarma junto con sus atributos (batería, comunicación, etc.) [aquí](https://github.com/AuroreVgn/somfy-protexial/blob/main/assets/Template%20Home%20Assistant).

<img width="485" height="127" alt="image" src="https://github.com/user-attachments/assets/d4f385c0-0171-4968-b369-c4cb86d8409e" />

### Compatibilidad de versiones

La lista de compatibilidad mostrada al principio de esta página **no es exhaustiva**. Es muy posible que esta integración sea compatible con otras versiones de las centrales Somfy. Si prueba otra versión con éxito, no dude en comunicármelo.

El año o la generación de la interfaz web de su central aparece en la parte inferior de las páginas:

<img src="assets/version.png" width="30%">

Algunas centrales también proporcionan su versión de firmware mediante la siguiente URL:

*http://192.168.1.234/cfg/vers*

o

*http://192.168.1.234:9876/cfg/vers*

### Uso de la interfaz web original

⚠️ **La central solo admite una sesión de usuario activa al mismo tiempo. Si desea utilizar la interfaz web original, deberá desactivar temporalmente esta integración.**

### Uso de la aplicación móvil oficial

⚠️ La aplicación oficial **Somfy Alarme** puede seguir utilizándose aunque la integración esté activa.

⚠️ La aplicación 'Somfy Alarme' dejará de funcionar cuando se [apaguen los servidores de Somfy](https://github.com/AuroreVgn/somfy-protexial/wiki/Arr%C3%AAt-de-la-2G-et-des-serveurs-alarmsomfy.eu-%E2%80%90-%C3%A9tude-d'impact-et-solution#arr%C3%AAt-des-serveurs-somfyalarmeu).

### Reconfiguración de la integración

La integración admite la reconfiguración completa directamente desde la interfaz gráfica de Home Assistant.

## ¡Las contribuciones son bienvenidas!

Si desea contribuir al proyecto, consulte las [Contribution guidelines](CONTRIBUTING.md).

## Créditos

Esta integración está basada en gran medida en el trabajo de [@Ludeeus](https://github.com/ludeeus) y en el proyecto [integration_blueprint][integration_blueprint].

---

[integration_blueprint]: https://github.com/custom-components/integration_blueprint
[hacs]: https://hacs.xyz
[hacsbadge]: https://img.shields.io/badge/HACS-Custom-orange.svg?style=flat-square
[license-shield]: https://img.shields.io/github/license/the8tre/somfy-protexial.svg?style=flat-square
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40the8tre-blue.svg?style=flat-square
[releases-shield]: https://img.shields.io/github/v/release/AuroreVgn/somfy-protexial.svg?style=flat-square
[releases]: https://github.com/AuroreVgn/somfy-protexial/releases
[user_profile]: https://github.com/AuroreVgn
