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

CHALLENGE_REGEX = r"[A-F]{1}[1-5]{1}"

HTTP_TIMEOUT = 10

# DOUBLON AVEC LES FICHIERS xxx_api.py
LIST_ELEMENTS = "/fr/u_plistelmt.htm"
LIST_ELEMENTS_PRINT = "/fr/p_ulistelem.htm"
LIST_ELEMENTS_ALT = "/fr/u_listelmt.htm"  # variante vue sur d'autres firmwares


class SomfyError(str, Enum):
    WRONG_CODE = "(0x0B00)"
    MAX_LOGIN_ATTEMPS = "(0x0904)"
    WRONG_CREDENTIALS = "(0x0812)"
    SESSION_ALREADY_OPEN = "(0x0902)"
    NOT_AUTHORIZED = "(0x0903)"
    UNKNOWN_PARAMETER = "(0x1003)"


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
        "state_on": "Détecté",
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
        "id": "box",
        "name": "Centrale",  # Amended to be clearer
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "icon_on": "mdi:alert-circle",
        "icon_off": "mdi:check-circle",
        "off_if": "ok",
        "state_on": "Problème",  # Amended to be clearer
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
]
