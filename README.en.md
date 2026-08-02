# Somfy Protexial / Protexiom / Protexial IO

[Français](README.md) | [English](README.en.md) | [Deutsch](README.de.md) | [Español](README.es.md) | [Italiano](README.it.md) | [Nederlands](README.nl.md) | [Português](README.pt.md)

## About

This integration allows Home Assistant to communicate with a Somfy Protexial, Protexiom or Protexial IO alarm control panel.

### Tested models

| Model | Version | Status |
|---|---:|:---:|
| Protexial IO | `2013 (v10_13)` | ✅ |
| Protexiom 5000 | `2013 (v10_3)` | ✅ |
| Protexiom | `2013 (v10_15)` | ✅ |
| Protexial | `2010 (v8_1)` | ✅ |
| Protexiom | `2008` | ✅ |

This list is not exhaustive. The integration may also work with other Somfy control panel versions.

### Supported features

- Alarm control by zones A, B and C
- Roller shutter control
- Light control
- Reading the overall control panel status
- Reading faults and states reported by Somfy devices

### Main entities

| Entity | Description |
|---|---|
| `alarm_control_panel` | `armed_away`, `armed_home`, `armed_night` and disarm modes |
| `cover` | Open, close and stop shutters, without position control |
| `light` | Turn lights on and off |
| `binary_sensor` | Battery, motion, opening, tamper, radio, GSM, camera and aggregated device states |
| `sensor` | GSM operator, GSM signal quality and last synchronization |
| `button` | Reset battery, alarm and radio-link faults |

## Installation

### Option A — HACS installation (recommended)

1. Open **Integrations** in HACS.
2. Open the **⋮** menu, then **Custom repositories**.
3. Add `https://github.com/AuroreVgn/somfy-protexial`.
4. Select the **Integration** category.
5. Search for **Somfy Protexial** and download the integration.
6. Restart Home Assistant.

### Option B — Manual installation

1. Download the archive from the latest available release.
2. Locate the directory containing `configuration.yaml`.
3. Create `custom_components` if it does not exist.
4. Create `custom_components/somfy_protexial`.
5. Extract the integration files into that directory.
6. Restart Home Assistant.

## Configuration

In Home Assistant, open:

**Settings → Devices & services → Add integration → Somfy Protexial**

### 1. Control panel address

Enter the local URL of the control panel web interface, for example:

```text
http://192.168.1.234
```

Include the port in the URL when your control panel uses a non-standard port.

### 2. Authentication

Depending on the control panel generation, the setup flow may request:

- the user-account password;
- the code matching the authentication-card challenge;
- on some older Protexiom panels, an administrator step followed by the user password.

### 3. Additional configuration

Arming modes use the zones configured in the Somfy control panel:

- **Away**: zones A + B + C;
- **Night**: optional zone combination;
- **Home**: optional zone combination.

An arming code can be configured and will then be requested when arming or disarming.

The polling interval can be set from 15 seconds to 1 hour. The default is 60 seconds.

## Important information

### Compatibility

The tested-model list is not exhaustive. Report successful use with another version in the repository issues or in the [HACF discussion thread](https://forum.hacf.fr/t/integration-custom-centrale-somfy-protexial/23589).

The interface year is generally displayed at the bottom of the control panel pages. Some panels also expose their version at:

```text
http://CONTROL_PANEL_ADDRESS/cfg/vers
```

### Using the original Somfy web interface

The control panel generally supports only one user session at a time. Temporarily disable or reload the integration before using the original web interface if the connection is refused.

### Reconfiguration

The integration can be reconfigured from the Home Assistant user interface.

## Contributing

Contributions, bug reports and compatibility feedback are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

## Credits

The initial code is based in part on Ludeeus’s `integration_blueprint` template.

## License

This project is released under the MIT License. See [LICENSE](LICENSE).
