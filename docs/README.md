# Documentation

Start with the [project README](../README.md) to install and run the desktop app.

| Guide | Purpose |
| --- | --- |
| [Stable LAN name](LAN_NAME.md) | Share apk-builder.local instead of a changing numeric IP. |
| [Windows startup](STARTUP.md) | Run the server automatically in the background without opening a browser. |
| [LAN server](SERVER.md) | Host the browser dashboard, configure access controls, and operate the durable build queue. |
| [Standalone configuration](CONFIGURATION.md) | Run a single executable, locate user settings, and migrate existing installations. |
| [Slack setup](integrations/SLACK.md) | Connect a Slack channel, configure the webhook, and troubleshoot delivery. |
| [Integration reference](INTEGRATIONS.md) | Configuration keys and behavior of every delivery and notification adapter. |
| [Architecture](ARCHITECTURE.md) | Build execution, UI events, persistence, and adapter extension points. |

For local verification, run `python -m unittest discover -s tests -v` and `python tests/gui_smoke.py` from the project root. HTTP calls in regression tests are mocked; these commands do not post to Slack or other notification channels.
