# Somfy Protexial / Protexiom / Protexial IO

[Français](README.md) | [English](README.en.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Italiano](README.it.md) | [Nederlands](README.nl.md) | [Português](README.pt.md)

## Over deze integratie

Met deze integratie kan Home Assistant communiceren met een Somfy Protexial-, Protexiom- of Protexial IO-alarmcentrale.

### Geteste modellen

| Model | Versie | Status |
|---|---:|:---:|
| Protexial IO | `2013 (v10_13)` | ✅ |
| Protexiom 5000 | `2013 (v10_3)` | ✅ |
| Protexiom | `2013 (v10_15)` | ✅ |
| Protexial | `2010 (v8_1)` | ✅ |
| Protexiom | `2008` | ✅ |

Deze lijst is niet volledig. De integratie kan ook met andere versies van Somfy-alarmcentrales werken.

### Ondersteunde functies

- Alarmbediening via zones A, B en C
- Bediening van rolluiken
- Bediening van verlichting
- Uitlezen van de algemene status van de centrale
- Uitlezen van storingen en statussen van Somfy-apparaten

### Belangrijkste entiteiten

| Entiteit | Beschrijving |
|---|---|
| `alarm_control_panel` | Modi `armed_away`, `armed_home`, `armed_night` en uitschakelen |
| `cover` | Rolluiken openen, sluiten en stoppen, zonder positieregeling |
| `light` | Verlichting in- en uitschakelen |
| `binary_sensor` | Batterij, beweging, opening, sabotage, radio, GSM, camera en samengevoegde apparaatstatussen |
| `sensor` | GSM-provider, GSM-signaalkwaliteit en laatste synchronisatie |
| `button` | Batterij-, alarm- en radioverbindingsstoringen resetten |

## Installatie

### Optie A — Installatie via HACS (aanbevolen)

1. Open **Integraties** in HACS.
2. Open het menu **⋮** en daarna **Aangepaste repositories**.
3. Voeg `https://github.com/AuroreVgn/somfy-protexial` toe.
4. Selecteer de categorie **Integratie**.
5. Zoek naar **Somfy Protexial** en download de integratie.
6. Start Home Assistant opnieuw op.

### Optie B — Handmatige installatie

1. Download het archief van de nieuwste beschikbare versie.
2. Zoek de map met `configuration.yaml`.
3. Maak `custom_components` aan als deze map nog niet bestaat.
4. Maak `custom_components/somfy_protexial` aan.
5. Pak de integratiebestanden in deze map uit.
6. Start Home Assistant opnieuw op.

## Configuratie

Open in Home Assistant:

**Instellingen → Apparaten & diensten → Integratie toevoegen → Somfy Protexial**

### 1. Adres van de alarmcentrale

Voer de lokale URL van de webinterface in, bijvoorbeeld:

```text
http://192.168.1.234
```

Voeg de poort aan de URL toe wanneer de centrale een afwijkende poort gebruikt.

### 2. Authenticatie

Afhankelijk van de generatie van de centrale kan de configuratie vragen om:

- het wachtwoord van het gebruikersaccount;
- de code die overeenkomt met de uitdaging op de authenticatiekaart;
- bij sommige oudere Protexiom-centrales eerst een beheerdersstap en daarna het gebruikerswachtwoord.

### 3. Aanvullende configuratie

De inschakelmodi gebruiken de zones die in de Somfy-centrale zijn ingesteld:

- **Afwezig**: zones A + B + C;
- **Nacht**: optionele zonecombinatie;
- **Thuis**: optionele zonecombinatie.

Er kan een inschakelcode worden ingesteld. Deze wordt vervolgens gevraagd bij het in- of uitschakelen.

Het update-interval kan worden ingesteld van 15 seconden tot 1 uur. De standaardwaarde is 60 seconden.

## Belangrijke informatie

### Compatibiliteit

De lijst met geteste modellen is niet volledig. Meld succesvolle werking met een andere versie via de issues van de repository of in het [HACF-discussieonderwerp](https://forum.hacf.fr/t/integration-custom-centrale-somfy-protexial/23589).

Het jaar van de interface staat meestal onderaan de pagina’s van de centrale. Sommige centrales tonen hun versie ook op:

```text
http://ADRES_VAN_DE_CENTRALE/cfg/vers
```

### De oorspronkelijke Somfy-webinterface gebruiken

De centrale ondersteunt doorgaans slechts één gebruikerssessie tegelijk. Schakel de integratie tijdelijk uit of laad deze opnieuw voordat je de oorspronkelijke webinterface gebruikt wanneer de verbinding wordt geweigerd.

### Opnieuw configureren

De integratie kan via de Home Assistant-interface opnieuw worden geconfigureerd.

## Bijdragen

Bijdragen, foutrapporten en compatibiliteitsfeedback zijn welkom. Lees [CONTRIBUTING.md](CONTRIBUTING.md) voordat je wijzigingen indient.

## Credits

De oorspronkelijke code is gedeeltelijk gebaseerd op Ludeeus’ `integration_blueprint`-sjabloon.

## Licentie

Dit project wordt uitgebracht onder de MIT-licentie. Zie [LICENSE](LICENSE).
