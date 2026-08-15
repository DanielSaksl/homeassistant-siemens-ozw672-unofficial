# Siemens OZW672 Unofficial — Enhanced Fork

**Version: 0.4.0-beta2**

[![HACS Custom][hacs-badge]][hacs]
[![License: MIT][license-badge]][license]

An unofficial, community-maintained enhanced fork of the [original Siemens
OZW672 Home Assistant integration][upstream]. It connects Home Assistant to a
local Siemens OZW672 gateway and lets you choose the datapoints that Home
Assistant should manage.

This project is independent of Siemens AG and is not affiliated with,
endorsed by, sponsored by, or approved by Siemens AG or its subsidiaries.

## What this fork does

- Connects to an OZW672 gateway through its local API.
- Creates `sensor`, `binary_sensor`, `number`, `select`, and `switch` entities
  when supported by the selected datapoint metadata.
- Supports writes for compatible `number`, `select`, and `switch` datapoints
  when the gateway reports that the datapoint is writable. The gateway can
  still reject a write.
- Uses the **Datapoint Browser** to add datapoints explicitly, individually or in batches.
- Polls only the datapoints that you have added. Opening the integration does
  not create or continuously poll the full OZW menu tree.

## Datapoint Browser

After the connection has been created, open **Settings → Devices & services →
Siemens OZW672 (Unofficial) → Configure** and choose **Datapoint Browser**.

The browser loads the OZW menu tree for that session, lets you search by
datapoint ID, name, or operation line, and select one or more datapoints. It
loads metadata only for the selected datapoints and shows it before they are
added. Only after confirmation are the datapoints saved and included in normal
polling.
Use **Remove Datapoint** from the same Configure menu to stop polling a saved
datapoint and remove its entity.

## Installation with HACS

1. Install [HACS][hacs] if it is not already installed.
2. Open **HACS → Integrations**, select the three-dot menu, then choose
   **Custom repositories**.
3. Add `https://github.com/DanielSaksl/homeassistant-siemens-ozw672-unofficial`
   with category **Integration**.
4. Find **Siemens OZW672 Unofficial** in HACS and install it.
5. Restart Home Assistant.

## First configuration

1. In Home Assistant, open **Settings → Devices & services → Add integration**.
2. Search for **Siemens OZW672 (Unofficial)**.
3. Enter the gateway host, OZW username, password, and preferred polling
   interval. The minimum interval is 10 seconds.
4. Open **Configure**, choose **Datapoint Browser**, and add only the
   datapoints you need.

Using a dedicated OZW account for Home Assistant is recommended. Start with a
small number of datapoints; the gateway may take noticeable time to browse or
serve a large menu tree.

## Known limitations / Beta

- This is an early public beta. Please report reproducible problems in the
  [issue tracker][issues].
- The browser scans the OZW menu tree only when it is opened. This may be slow
  on some gateways.
- Entity type and write availability depend on the metadata returned by the
  gateway. Not every datapoint is writable.
- The current API client does not enforce TLS certificate verification.

## Development

This project is developed with the assistance of AI tools, including OpenAI
Codex. AI-assisted development is used for code changes, debugging, testing,
and documentation. All changes are reviewed and tested by the maintainer.

**Original project:** John Ahern Infotrack<br>
**This fork:** Daniel Saksl<br>
**AI assistance:** OpenAI Codex

## Credits and licence

This fork is based on the original [Siemens OZW672 integration by John Ahern
Infotrack][upstream]. The original project, its author, and its attribution are
preserved in this repository.

The project remains available under the [MIT License][license]. It is provided
without warranty; use it and any changes it sends to your equipment at your
own risk.

"Siemens", "OZW672", and related product names are trademarks of their
respective owners and are used only to identify compatible hardware. The icons
and logos in this repository are original project artwork, not Siemens assets.

[hacs]: https://hacs.xyz/docs/use/
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-orange.svg
[issues]: https://github.com/DanielSaksl/homeassistant-siemens-ozw672-unofficial/issues
[license]: LICENSE
[license-badge]: https://img.shields.io/badge/License-MIT-yellow.svg
[upstream]: https://github.com/johnaherninfotrack/homeassistant_custom_siemensozw672
