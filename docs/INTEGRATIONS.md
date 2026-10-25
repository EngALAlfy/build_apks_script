# Integration reference

Delivery providers produce download links; notification adapters announce those links. Configure them in **Distribution**. No `.env` is required; saved configuration lives in your user profile. All flags default to `false`. Clearing a UI field and saving clears its stored setting. Settings are locked during builds.

## Provider matrix

| Integration | Role | Required when enabled | Optional configuration |
| --- | --- | --- | --- |
| MEGA | Artifact upload | `MEGA_USERNAME`, `MEGA_PASSWORD` | None |
| FTP | Artifact upload | `FTP_HOST`, `FTP_USER`, `FTP_PASS`, `FTP_BASE_URL` | `FTP_PATH` (defaults to `/`) |
| Discord | Artifact notification | `DISCORD_WEBHOOK` | None |
| Slack | Artifact notification | `SLACK_WEBHOOK` | None |
| Email | Artifact notification | `EMAILS`, `SMTP_HOST`, `SMTP_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD` | None |

Enable with `MEGA_ENABLED`, `FTP_ENABLED`, `DISCORD_ENABLED`, `SLACK_ENABLED`, or `EMAIL_ENABLED`. The names in [`.env.example`](../.env.example) also document supported environment variables and the optional legacy import format; the file is not required beside the executable.

## Build and delivery order

1. Synchronize the repository and build each selected format.
2. Copy each artifact to its output session directory and immediately record local history.
3. Upload artifacts using enabled delivery providers, with at most three upload workers.
4. Persist returned URLs and tracked MEGA handles.
5. Attempt Slack, Discord, and email announcements for artifacts with returned URLs.
6. Persist the Slack acknowledgement flag and Discord message IDs when available.
7. Report complete, warning, failed, or cancelled through the coordinator event queue.

Slack is attempted before Discord and email. Its expected transport errors return a failed acknowledgement so other notifications can continue. Missing delivery results or failed notifications cause warnings without discarding collected local files.

## Adapter details

### MEGA

The SDK is imported only when used. Uploaded filenames retain `.apk` or `.aab`. History records deletion handles when returned by the SDK. A running MEGA operation may delay cancellation.

### FTP

The current adapter uses FTP with a 30-second socket timeout. `FTP_HOST` is a hostname, `FTP_PATH` selects the server directory, and `FTP_BASE_URL` is the download prefix, not the upload hostname. Transfer callbacks update progress and check cancellation. FTP artifacts require separate deletion on the server.

### Slack

See [Slack setup and behavior](integrations/SLACK.md). The adapter uses `requests` already present in requirements; no bot token or Slack SDK is required. Slack has no automatic message cleanup through this adapter.

### Discord

Incoming webhooks receive build embeds and download links. Successful response IDs are retained for later cleanup. Requests use a 30-second timeout. Deleting an already absent message is treated as completed cleanup.

### Email

`EMAILS` accepts comma-separated recipients. The adapter logs into SMTP using STARTTLS, sends an HTML build report, and uses a 30-second timeout. Notifications cannot be recalled through artifact cleanup.

## Credentials and logs

Settings are stored as JSON in `%LOCALAPPDATA%\APKBuilder\settings.json`. This is local configuration storage, not a secrets vault: configured credentials are stored as plain strings. Keep the profile file private and do not commit or bundle it. An optional legacy `.env` is imported on first use; it is never created or updated by the app. Password/webhook fields are masked and known secrets are redacted in the desktop Console and exported logs. Redaction is a safeguard rather than a reason to share credentials or unrestricted logs.

## Extension contract

Add an adapter under `modules/`, declare required fields in `SERVICE_FIELDS`, add its controls in the Distribution page, add secrets to `SECRET_KEYS`, and wire its outcome into the coordinator. Use bounded network timeouts, keep widgets out of workers, and report failures without deleting local artifacts. Add mocked adapter and coordinator tests and update `.env.example` and these docs together.
