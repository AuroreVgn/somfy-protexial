# Somfy Protexial / Protexiom / Protexial IO

[Français](README.md) | [English](README.en.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Italiano](README.it.md) | [Nederlands](README.nl.md) | [Português](README.pt.md)

## Über diese Integration

Diese Integration ermöglicht Home Assistant die Kommunikation mit einer Somfy-Protexial-, Protexiom- oder Protexial-IO-Alarmzentrale.

### Getestete Modelle

| Modell | Version | Status |
|---|---:|:---:|
| Protexial IO | `2013 (v10_13)` | ✅ |
| Protexiom 5000 | `2013 (v10_3)` | ✅ |
| Protexiom | `2013 (v10_15)` | ✅ |
| Protexial | `2010 (v8_1)` | ✅ |
| Protexiom | `2008` | ✅ |

Diese Liste ist nicht vollständig. Die Integration kann auch mit weiteren Versionen von Somfy-Alarmzentralen funktionieren.

### Unterstützte Funktionen

- Alarmsteuerung über die Zonen A, B und C
- Steuerung von Rollläden
- Steuerung von Beleuchtung
- Auslesen des allgemeinen Zentralenstatus
- Auslesen von Fehlern und Zuständen der Somfy-Komponenten

### Wichtigste Entitäten

| Entität | Beschreibung |
|---|---|
| `alarm_control_panel` | Modi `armed_away`, `armed_home`, `armed_night` und Unscharfschaltung |
| `cover` | Öffnen, Schließen und Stoppen der Rollläden, ohne Positionssteuerung |
| `light` | Beleuchtung ein- und ausschalten |
| `binary_sensor` | Batterie, Bewegung, Öffnung, Sabotage, Funk, GSM, Kamera und zusammengefasste Gerätezustände |
| `sensor` | GSM-Anbieter, GSM-Signalqualität und letzte Synchronisierung |
| `button` | Zurücksetzen von Batterie-, Alarm- und Funkverbindungsfehlern |

## Installation

### Option A — Installation über HACS (empfohlen)

1. Öffnen Sie in HACS **Integrationen**.
2. Öffnen Sie das Menü **⋮** und danach **Benutzerdefinierte Repositories**.
3. Fügen Sie `https://github.com/AuroreVgn/somfy-protexial` hinzu.
4. Wählen Sie die Kategorie **Integration**.
5. Suchen Sie nach **Somfy Protexial** und laden Sie die Integration herunter.
6. Starten Sie Home Assistant neu.

### Option B — Manuelle Installation

1. Laden Sie das Archiv der neuesten verfügbaren Version herunter.
2. Suchen Sie das Verzeichnis mit `configuration.yaml`.
3. Erstellen Sie `custom_components`, falls das Verzeichnis noch nicht existiert.
4. Erstellen Sie `custom_components/somfy_protexial`.
5. Entpacken Sie die Integrationsdateien in dieses Verzeichnis.
6. Starten Sie Home Assistant neu.

## Konfiguration

Öffnen Sie in Home Assistant:

**Einstellungen → Geräte & Dienste → Integration hinzufügen → Somfy Protexial**

### 1. Adresse der Alarmzentrale

Geben Sie die lokale URL der Weboberfläche ein, zum Beispiel:

```text
http://192.168.1.234
```

Verwendet die Zentrale einen besonderen Port, fügen Sie ihn der URL hinzu.

### 2. Authentifizierung

Je nach Generation der Zentrale kann der Einrichtungsdialog Folgendes verlangen:

- das Passwort des Benutzerkontos;
- den zur Authentifizierungskarte passenden Challenge-Code;
- bei einigen älteren Protexiom-Zentralen zunächst einen Administrator-Schritt und anschließend das Benutzerpasswort.

### 3. Zusätzliche Konfiguration

Die Scharfschaltmodi verwenden die in der Somfy-Zentrale eingerichteten Zonen:

- **Abwesend**: Zonen A + B + C;
- **Nacht**: optionale Zonenkombination;
- **Anwesend**: optionale Zonenkombination.

Ein Scharfschaltcode kann festgelegt werden. Er wird dann beim Scharf- oder Unscharfschalten verlangt.

Das Abfrageintervall kann zwischen 15 Sekunden und 1 Stunde eingestellt werden. Standardwert sind 60 Sekunden.

## Wichtige Hinweise

### Kompatibilität

Die Liste der getesteten Modelle ist nicht vollständig. Erfolgreiche Tests mit einer anderen Version können in den Issues des Repositories oder im [HACF-Diskussionsthread](https://forum.hacf.fr/t/integration-custom-centrale-somfy-protexial/23589) gemeldet werden.

Das Jahr der Oberfläche wird normalerweise unten auf den Seiten der Zentrale angezeigt. Einige Zentralen stellen ihre Version auch unter folgender Adresse bereit:

```text
http://ADRESSE_DER_ZENTRALE/cfg/vers
```

### Verwendung der ursprünglichen Somfy-Weboberfläche

Die Zentrale unterstützt normalerweise nur eine Benutzersitzung gleichzeitig. Deaktivieren oder laden Sie die Integration vorübergehend neu, bevor Sie die ursprüngliche Weboberfläche verwenden, falls die Verbindung abgelehnt wird.

### Neukonfiguration

Die Integration kann über die Home-Assistant-Oberfläche neu konfiguriert werden.

## Beiträge

Beiträge, Fehlerberichte und Kompatibilitätsrückmeldungen sind willkommen. Lesen Sie vor Änderungen [CONTRIBUTING.md](CONTRIBUTING.md).

## Danksagung

Der ursprüngliche Code basiert teilweise auf Ludeeus’ Vorlage `integration_blueprint`.

## Lizenz

Dieses Projekt wird unter der MIT-Lizenz veröffentlicht. Siehe [LICENSE](LICENSE).
