# Slack integration

APK Builder posts a notification for each successfully collected artifact that has a valid HTTP or HTTPS download link from a delivery provider. Messages include the application, build format, branch, session, filename, and download links. Local directory paths, build logs, and credentials are excluded.

## Connect a channel

1. Create or select a Slack app in your workspace.
2. Enable **Incoming Webhooks** in its settings.
3. Choose **Add New Webhook to Workspace**, select the destination channel, and authorize it. Private channels require channel membership.
4. Copy the generated webhook URL.
5. In APK Builder, open **Distribution**, enable **Slack notifications**, paste the URL, and save settings. Enable and configure MEGA or FTP delivery as well.
6. Select a project and build format, then use **Build settings > Validate setup** before building.

Follow Slack's [official incoming webhook guide](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/) for workspace administration and authorization details. The webhook determines the channel; the app does not accept a separate channel override.

## Configuration

Enter these settings in **Distribution** and save. The names below also work as environment variables or optional legacy `.env` imports; no `.env` file is required for the executable.

```dotenv
SLACK_ENABLED=true
SLACK_WEBHOOK=YOUR_GENERATED_SLACK_WEBHOOK_URL
```

Replace the placeholder with the generated URL. Accepted endpoints use HTTPS and either `hooks.slack.com/services/...` or `hooks.slack-gov.com/services/...`. Other hosts, embedded user credentials, query strings, and fragments are rejected. `SLACK_ENABLED` defaults to `false` for existing configurations.

The field is masked in the desktop app. Settings are stored in `%LOCALAPPDATA%\APKBuilder\settings.json`. The webhook is a credential: keep this profile file private, keep it out of Git, and rotate the webhook through Slack if it is exposed. The app never embeds your webhook in the executable. The app redacts configured webhook values and recognizable Slack webhook URLs from displayed/exported logs.

## Delivery contract

- One POST is attempted per artifact with usable download links after delivery results are recorded.
- Rich blocks carry metadata and links. Automatic link/media previews are disabled.
- FTP delivery must expose a public HTTP or HTTPS download base URL for Slack links. Authenticated URL credentials and malformed link targets are excluded.
- HTTP 200 with a plain `ok` body is the only acknowledged success.
- Connect/read timeouts are 5/20 seconds. Redirects are not followed.
- Errors produce a build warning and retain the local artifact and download URLs. A later project can still proceed.
- No automatic retries occur. Timeouts have an unknown delivery outcome; inspect the channel before retrying to avoid duplicates.
- Artifact history gains `slack_notified: true` on acknowledgement or `false` on an unacknowledged attempt. This is an acknowledgement flag, not a Slack message ID.
- Cancellation is checked between artifact operations. A running webhook request may finish before cancellation takes effect.

Slack is an artifact-ready notification channel in this version. Local-only builds, failed builds, cancelled builds, and unsuccessful uploads do not generate separate Slack alerts. Enabling Slack requires MEGA or FTP delivery under the app's current notification contract.

## Cleanup and history

Slack incoming webhooks do not return a message ID or support deleting posted messages. Artifact cleanup and **Forget record** leave Slack posts in the channel. The cleanup confirmation explains this for acknowledged Slack notifications. Use Slack directly to remove old posts if your workspace permits it. See Slack's [webhook limitations](https://docs.slack.dev/messaging/sending-messages-using-incoming-webhooks/).

## Troubleshooting

| Symptom | Action |
| --- | --- |
| Validation reports a missing or invalid webhook | Paste the generated incoming webhook URL and save settings. |
| Validation requires delivery | Enable MEGA or FTP and complete its required settings. |
| Build warning with HTTP 403 or 404 | Check workspace restrictions, channel availability, and webhook configuration. |
| Rate limit warning | Wait and check the channel before retrying. |
| Timeout or connection warning | Check network/proxy access and the channel; the message may already exist. |
| No valid download link | Configure an HTTP/HTTPS FTP base URL or MEGA delivery. |
| New executable shows no Slack settings | Run the updated source or rebuild using `main.spec`. |

The tests in `tests/test_slack_integration.py` cover URL validation, payload formatting, HTTP acknowledgement, timeouts, rate limits, redaction, and build-service outcomes. All network calls are mocked. A real delivery check requires your own webhook and an intentional build; the regression suite does not post test messages.
