# Somfy Protexial / Protexiom / Protexial IO

[Français](README.md) | [English](README.en.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Italiano](README.it.md) | [Nederlands](README.nl.md) | [Português](README.pt.md)

## Informazioni

Questa integrazione consente a Home Assistant di comunicare con una centrale di allarme Somfy Protexial, Protexiom o Protexial IO.

### Modelli testati

| Modello | Versione | Stato |
|---|---:|:---:|
| Protexial IO | `2013 (v10_13)` | ✅ |
| Protexiom 5000 | `2013 (v10_3)` | ✅ |
| Protexiom | `2013 (v10_15)` | ✅ |
| Protexial | `2010 (v8_1)` | ✅ |
| Protexiom | `2008` | ✅ |

Questo elenco non è esaustivo. L’integrazione può funzionare anche con altre versioni delle centrali Somfy.

### Funzioni supportate

- Controllo dell’allarme tramite le zone A, B e C
- Controllo delle tapparelle
- Controllo delle luci
- Lettura dello stato generale della centrale
- Lettura di guasti e stati dei dispositivi Somfy

### Entità principali

| Entità | Descrizione |
|---|---|
| `alarm_control_panel` | Modalità `armed_away`, `armed_home`, `armed_night` e disinserimento |
| `cover` | Apertura, chiusura e arresto delle tapparelle, senza controllo della posizione |
| `light` | Accensione e spegnimento delle luci |
| `binary_sensor` | Batteria, movimento, apertura, manomissione, radio, GSM, telecamera e stati aggregati dei dispositivi |
| `sensor` | Operatore GSM, qualità del segnale GSM e ultima sincronizzazione |
| `button` | Ripristino dei guasti batteria, allarme e collegamento radio |

## Installazione

### Opzione A — Installazione tramite HACS (consigliata)

1. Apri **Integrazioni** in HACS.
2. Apri il menu **⋮**, quindi **Repository personalizzati**.
3. Aggiungi `https://github.com/AuroreVgn/somfy-protexial`.
4. Seleziona la categoria **Integrazione**.
5. Cerca **Somfy Protexial** e scarica l’integrazione.
6. Riavvia Home Assistant.

### Opzione B — Installazione manuale

1. Scarica l’archivio dell’ultima versione disponibile.
2. Individua la cartella contenente `configuration.yaml`.
3. Crea `custom_components` se non esiste.
4. Crea `custom_components/somfy_protexial`.
5. Estrai i file dell’integrazione in questa cartella.
6. Riavvia Home Assistant.

## Configurazione

In Home Assistant apri:

**Impostazioni → Dispositivi e servizi → Aggiungi integrazione → Somfy Protexial**

### 1. Indirizzo della centrale

Inserisci l’URL locale dell’interfaccia web della centrale, ad esempio:

```text
http://192.168.1.234
```

Se la centrale utilizza una porta particolare, includila nell’URL.

### 2. Autenticazione

A seconda della generazione della centrale, la procedura può richiedere:

- la password dell’account utente;
- il codice corrispondente alla richiesta della scheda di autenticazione;
- su alcune vecchie Protexiom, un passaggio amministratore seguito dalla password utente.

### 3. Configurazione aggiuntiva

Le modalità di inserimento utilizzano le zone configurate nella centrale Somfy:

- **Fuori casa**: zone A + B + C;
- **Notte**: combinazione opzionale di zone;
- **In casa**: combinazione opzionale di zone.

È possibile definire un codice di inserimento, che verrà richiesto durante l’inserimento o il disinserimento.

L’intervallo di aggiornamento può essere impostato da 15 secondi a 1 ora. Il valore predefinito è 60 secondi.

## Informazioni importanti

### Compatibilità

L’elenco dei modelli testati non è esaustivo. Puoi segnalare il funzionamento con un’altra versione nelle issue del repository o nel [thread di discussione HACF](https://forum.hacf.fr/t/integration-custom-centrale-somfy-protexial/23589).

L’anno dell’interfaccia è generalmente visibile in fondo alle pagine della centrale. Alcune centrali espongono inoltre la versione all’indirizzo:

```text
http://INDIRIZZO_DELLA_CENTRALE/cfg/vers
```

### Uso dell’interfaccia web originale Somfy

La centrale supporta generalmente una sola sessione utente alla volta. Disabilita o ricarica temporaneamente l’integrazione prima di usare l’interfaccia web originale se la connessione viene rifiutata.

### Riconfigurazione

L’integrazione può essere riconfigurata dall’interfaccia di Home Assistant.

## Contributi

Contributi, segnalazioni di errori e feedback sulla compatibilità sono benvenuti. Leggi [CONTRIBUTING.md](CONTRIBUTING.md) prima di proporre modifiche.

## Crediti

Il codice iniziale si basa in parte sul modello `integration_blueprint` di Ludeeus.

## Licenza

Questo progetto è distribuito con licenza MIT. Consulta [LICENSE](LICENSE).
