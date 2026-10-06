"""Localization helpers for extra state attributes.

Home Assistant does not translate arbitrary extra-state attribute keys/values from
translations/*.json, so these UI-only strings are centralized here. Protocol/raw
values remain unchanged.
"""

ATTRIBUTE_LOCALIZATION = {
    "fr": {
        "element_labels": {"battery": "Batterie", "comm": "Communication radio", "house": "Défaut", "tamper": "Autoprotection", "door": "Ouverture", "pause": "Actif", "zone": "Zone"},
        "element_values": {"ok": "OK", "low": "Faible", "connected": "Connecté", "disconnected": "Déconnecté", "domestic fault/intrusion": "Défaut/Intrusion", "open/ripped off": "Ouvert/Arraché", "closed": "Fermé", "open": "Ouvert", "running": "Actif", "paused": "En pause"},
        "datetime_labels": {"datetime": "Date et heure de la centrale", "date": "Date de la centrale", "time": "Heure de la centrale"},
    },
    "de": {
        "element_labels": {"battery": "Batterie", "comm": "Funkverbindung", "house": "Störung", "tamper": "Sabotage", "door": "Öffnung", "pause": "Aktiv", "zone": "Zone"},
        "element_values": {"ok": "OK", "low": "Niedrig", "connected": "Verbunden", "disconnected": "Getrennt", "domestic fault/intrusion": "Störung/Einbruch", "open/ripped off": "Offen/abgerissen", "closed": "Geschlossen", "open": "Geöffnet", "running": "Aktiv", "paused": "Pausiert"},
        "datetime_labels": {"datetime": "Datum und Uhrzeit der Zentrale", "date": "Datum der Zentrale", "time": "Uhrzeit der Zentrale"},
    },
    "es": {
        "element_labels": {"battery": "Batería", "comm": "Comunicación por radio", "house": "Fallo", "tamper": "Sabotaje", "door": "Apertura", "pause": "Activo", "zone": "Zona"},
        "element_values": {"ok": "OK", "low": "Baja", "connected": "Conectado", "disconnected": "Desconectado", "domestic fault/intrusion": "Fallo/Intrusión", "open/ripped off": "Abierto/Arrancado", "closed": "Cerrado", "open": "Abierto", "running": "Activo", "paused": "En pausa"},
        "datetime_labels": {"datetime": "Fecha y hora de la central", "date": "Fecha de la central", "time": "Hora de la central"},
    },
    "it": {
        "element_labels": {"battery": "Batteria", "comm": "Comunicazione radio", "house": "Guasto", "tamper": "Manomissione", "door": "Apertura", "pause": "Attivo", "zone": "Zona"},
        "element_values": {"ok": "OK", "low": "Bassa", "connected": "Connesso", "disconnected": "Disconnesso", "domestic fault/intrusion": "Guasto/Intrusione", "open/ripped off": "Aperto/Strappato", "closed": "Chiuso", "open": "Aperto", "running": "Attivo", "paused": "In pausa"},
        "datetime_labels": {"datetime": "Data e ora della centrale", "date": "Data della centrale", "time": "Ora della centrale"},
    },
    "nl": {
        "element_labels": {"battery": "Batterij", "comm": "Radioverbinding", "house": "Storing", "tamper": "Sabotage", "door": "Opening", "pause": "Actief", "zone": "Zone"},
        "element_values": {"ok": "OK", "low": "Laag", "connected": "Verbonden", "disconnected": "Niet verbonden", "domestic fault/intrusion": "Storing/Indringing", "open/ripped off": "Open/Losgetrokken", "closed": "Gesloten", "open": "Open", "running": "Actief", "paused": "Gepauzeerd"},
        "datetime_labels": {"datetime": "Datum en tijd van de centrale", "date": "Datum van de centrale", "time": "Tijd van de centrale"},
    },
    "pt": {
        "element_labels": {"battery": "Bateria", "comm": "Comunicação por rádio", "house": "Falha", "tamper": "Sabotagem", "door": "Abertura", "pause": "Ativo", "zone": "Zona"},
        "element_values": {"ok": "OK", "low": "Baixa", "connected": "Ligado", "disconnected": "Desligado", "domestic fault/intrusion": "Falha/Intrusão", "open/ripped off": "Aberto/Arrancado", "closed": "Fechado", "open": "Aberto", "running": "Ativo", "paused": "Em pausa"},
        "datetime_labels": {"datetime": "Data e hora da central", "date": "Data da central", "time": "Hora da central"},
    },
    "en": {
        "element_labels": {"battery": "Battery", "comm": "Radio link", "house": "Fault", "tamper": "Tamper", "door": "Opening", "pause": "Active", "zone": "Zone"},
        "element_values": {"ok": "OK", "low": "Low", "connected": "Connected", "disconnected": "Disconnected", "domestic fault/intrusion": "Fault/Intrusion", "open/ripped off": "Open/Ripped off", "closed": "Closed", "open": "Open", "running": "Active", "paused": "Paused"},
        "datetime_labels": {"datetime": "Centrale date and time", "date": "Centrale date", "time": "Centrale time"},
    },
}


def get_ha_language(entity) -> str:
    """Return a supported two-letter Home Assistant language code."""
    hass = getattr(entity, "hass", None)
    language = str(getattr(getattr(hass, "config", None), "language", None) or "en").lower()
    language = language.split("-")[0].split("_")[0]
    return language if language in ATTRIBUTE_LOCALIZATION else "en"


def get_attribute_localization(entity) -> dict:
    """Return UI localization for extra state attributes."""
    return ATTRIBUTE_LOCALIZATION[get_ha_language(entity)]
