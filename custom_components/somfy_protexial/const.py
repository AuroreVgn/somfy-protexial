from enum import Enum, auto

from homeassistant.components.binary_sensor import BinarySensorDeviceClass

# Added to handle sensors
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.const import EntityCategory

DOMAIN = "somfy_protexial"

CONF_API_TYPE = "api_type"
CONF_CODE = "code"
CONF_CODES = "codes"
CONF_MODES = "modes"
CONF_ARM_CODE = "arm_code"
CONF_NIGHT_ZONES = "night_zones"
CONF_HOME_ZONES = "home_zones"

API = "api"
COORDINATOR = "coordinator"
DEVICE_INFO = "device_info"

CHALLENGE_REGEX = r"\b[A-F][1-5]\b"

HTTP_TIMEOUT = 10

LIST_ELEMENTS = "/fr/u_plistelmt.htm"
LIST_ELEMENTS_PRINT = "/fr/p_ulistelem.htm"
LIST_ELEMENTS_NOLANG = (
    "/u_plistelmt.htm"  # variante vue sur d'autres firmwares sans le préfixe de langue
)
LIST_ELEMENTS_ALT = "/fr/u_listelmt.htm"  # variante vue sur d'autres firmwares
LIST_ELEMENTS_ALT_NOLANG = (
    "/u_listelmt.htm"  # variante vue sur d'autres firmwares sans le préfixe de langue
)


class SomfyError(str, Enum):
    WRONG_CODE = "(0x0B00)"
    MAX_LOGIN_ATTEMPTS = "(0x0904)"
    WRONG_CREDENTIALS = "(0x0812)"
    SESSION_ALREADY_OPEN = "(0x0902)"
    NOT_AUTHORIZED = "(0x0903)"
    UNKNOWN_PARAMETER = "(0x1003)"
    WRONG_CODE_ALT = "(0x1101)"
    WRONG_CREDENTIALS_ALT = "(0x0901)"
    WRONG_CREDENTIALS_2_ALT = "(0x0810)"
    INSUFFICIENT_PERMISSIONS_ALT = "(0x0903)"
    UNEXPECTED_ERROR = "(0x0000)"


class Zone(Enum):
    NONE = 0
    A = 1
    B = 2
    C = 4
    ABC = 7


ALL_ZONES = ["0", "1", "2", "4", "3", "6", "5"]


class ApiType(str, Enum):
    PROTEXIAL = "protexial"
    PROTEXIOM = "protexiom"
    PROTEXIAL_IO = "protexial_io"
    PROTEXIOM_ALT = "protexiom_alt"


class Page(str, Enum):
    LOGIN = "login"
    LOGOUT = "logout"
    PILOTAGE = "pilotage"
    STATUS = "status"
    ERROR = "error"
    ELEMENTS = "elements"
    CHALLENGE_CARD = "challenge_card"
    VERSION = "version"
    DEFAULT = "default"


class Selector(str, Enum):
    CONTENT_TYPE = "content_type"
    LOGIN_CHALLENGE = "login_challenge"
    ERROR_CODE = "error_code"
    FOOTER = "footer"
    CHALLENGE_CARD = "challenge_card"


BINARY_SENSORS = [
    {
        "id": "battery",
        "name": "Batterie",
        "device_class": BinarySensorDeviceClass.BATTERY,
        "icon_on": "mdi:battery-alert",
        "icon_off": "mdi:battery",
        "off_if": "ok",
        "state_on": "Vérifier la liste des éléments",  # Amended to be clearer
        "state_off": "OK",
    },
    {
        "id": "alarm",
        "name": "Mouvement",  # Amended to be clearer
        "device_class": BinarySensorDeviceClass.MOTION,
        "icon_on": "mdi:motion-sensor",
        "icon_off": "mdi:motion-sensor-off",
        "off_if": "ok",
        "state_on": "Detecté",
        "state_off": "Non détecté",
    },
    {
        "id": "door",
        "name": "Portes ou fenêtres",  # Amended to be clearer
        "device_class": BinarySensorDeviceClass.DOOR,
        "icon_on": "mdi:door-open",
        "icon_off": "mdi:door-closed",
        "off_if": "ok",
        "state_on": "Ouvertes",  # Amended to be clearer
        "state_off": "Fermées",  # Amended to be clearer
    },
    {
        # Jeedom's reference plugin (phpProtexiom.class.php) maps this same
        # status.xml tag (defaut4) to a dedicated "TAMPERED" info cmd with
        # device_class SABOTAGE: it is the centrale's box self-protection
        # (autoprotection) flag, not a generic problem flag. Renamed/
        # reclassified accordingly (was "Centrale" / PROBLEM).
        "id": "box",
        "name": "Autoprotection",
        "device_class": BinarySensorDeviceClass.TAMPER,
        "icon_on": "mdi:shield-alert",
        "icon_off": "mdi:shield-check",
        "off_if": "ok",
        "state_on": "Boîtier ouvert",
        "state_off": "OK",
    },
    {
        "id": "radio",
        "name": "Comm Centrale <-> Capteurs",  # Amended to be clearer
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "icon_on": "mdi:access-point",
        "icon_off": "mdi:access-point-off",
        "on_if": "ok",
        "state_on": "OK",
        "state_off": "Vérifier la liste des éléments",  # Amended to be clearer
    },
    {
        "id": "gsm",
        "name": "Communication GSM",  # Amended to be clearer
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "icon_on": "mdi:cellphone",
        "icon_off": "mdi:cellphone-off",
        "on_if": "gsm connect au rseau",  # Filtered: "GSM connecté au réseau"
        "state_on": "OK",  # Amended to be clearer
        "state_off": "Pas de réseau",  # Amended to be clearer
    },
    {
        "id": "camera",
        "name": "Caméra",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "icon_on": "mdi:webcam",
        "icon_off": "mdi:webcam-off",
        "on_if": "enabled",
        "state_on": "Connectée",
        "state_off": "Non connectée",
    },
]
# Added SENSOR platform for GSM Provider and GSM Signal Strength
SENSORS = [
    {
        "id": "opegsm",
        "name": "Opérateur GSM",
        "device_class": SensorDeviceClass.ENUM,
        "icon": "mdi:signal",
    },
    {
        "id": "recgsm",
        "name": "Signal GSM (/5)",
        "icon": "mdi:signal-2g",
    },
    {
        # Diagnostic entity mirroring Jeedom's lastCommunication/timeout
        # info (checkAndUpdateCmdProtexiom()): timestamp of the last poll
        # that successfully reached the centrale. Lets you spot a centrale
        # that has stopped responding without having to read the logs.
        "id": "last_sync",
        "name": "Dernière synchronisation",
        "device_class": SensorDeviceClass.TIMESTAMP,
        "icon": "mdi:clock-check-outline",
        "entity_category": EntityCategory.DIAGNOSTIC,
    },
]

# Buttons to acknowledge/reset the 3 "defaut" flags that the centrale never
# clears on its own (defaut0/battery, defaut1/radio, defaut3/alarm). Each
# "id" matches one-to-one with a SomfyProtexial.reset_xxx() coroutine name,
# itself based on the Jeedom plugin's EraseDefault commands
# (RESET_BATTERY_ERR / RESET_ALARM_ERR / RESET_LINK_ERR).
BUTTONS = [
    {
        "id": "reset_battery_err",
        "name": "Réinitialiser défaut piles",
        "icon": "mdi:battery-off-outline",
    },
    {
        "id": "reset_alarm_err",
        "name": "Réinitialiser défaut alarme",
        "icon": "mdi:alarm-light-off-outline",
    },
    {
        "id": "reset_link_err",
        "name": "Réinitialiser défaut liaison radio",
        "icon": "mdi:access-point-off",
    },
]
