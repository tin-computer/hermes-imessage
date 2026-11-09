# hermes-imessage

iMessage, RCS and SMS for [Hermes Agent](https://hermes-agent.nousresearch.com/), through [Claw Messenger](https://www.clawmessenger.com). No Mac and no SIM required: Hermes can run on Linux, in Docker or on a VPS.

Your Hermes agent can:

- Receive iMessages, RCS and SMS sent to your Claw Messenger number.
- Reply from that number, with iMessage first and RCS or SMS when the recipient can't get iMessage.
- Send to one-on-one chats and existing group chats.
- Create new group chats with the `claw_messenger_create_group` tool (Growth plan and above).
- Receive image, video, audio and document attachments as local files the agent's vision tools can read.

You need a Claw Messenger account and API key. Plans and limits are on the [pricing page](https://www.clawmessenger.com/pricing); first-time customers get a 7-day trial (card required).

## Install from the Hermes plugin catalog

```bash
hermes plugins install claw-messenger --enable
hermes gateway setup        # pick Claw Messenger, paste your API key
hermes gateway start
```

Get the API key from the [dashboard](https://www.clawmessenger.com/dashboard), then register the phone numbers that may text your agent there. Messages from numbers you haven't registered don't reach it.

To let the agent start new group chats, enable the toolset and map it onto the platform:

```bash
hermes tools enable hermes-claw-messenger
# then in ~/.hermes/config.yaml (merge with existing entries):
#   platform_toolsets:
#     claw_messenger:
#       - hermes-claw-messenger
```

## Install with pip (alternative)

```bash
# 1. Install into the Hermes venv.
#    Hermes (curl-installer) ships a uv-managed venv with no system pip,
#    so use uv with --python pointing at it:
uv pip install --python ~/.hermes/hermes-agent/venv hermes-imessage

# 2. Enable the plugin in ~/.hermes/config.yaml.
#    `hermes plugins enable` cannot currently see entry-point plugins, so
#    edit config.yaml directly (or run the one-liner below):
python3 -c "
from pathlib import Path
p = Path.home() / '.hermes' / 'config.yaml'
text = p.read_text() if p.exists() else ''
if 'imessage' not in text:
    p.write_text(text.rstrip() + '\n\nplugins:\n  enabled:\n    - imessage\n')
"

# 3. Enable the agent toolset so claw_messenger_create_group is reachable
hermes tools enable hermes-claw-messenger

# 4. Map the toolset onto the claw_messenger platform (merge with existing
#    platform_toolsets:; do not replace other entries).
#    Adds the block:
#      platform_toolsets:
#        claw_messenger:
#          - hermes-claw-messenger

# 5. Configure the API key (from https://clawmessenger.com/dashboard)
echo 'CLAW_MESSENGER_API_KEY=cm_live_…' >> ~/.hermes/.env

# 6. Start the gateway
hermes gateway start
```

Then register one or more phone numbers on the Claw Messenger dashboard so inbound messages reach your tenant.

## Configuration

All settings can be supplied via environment variables (preferred) or `~/.hermes/config.yaml`.

| Env var | Default | Purpose |
|---|---|---|
| `CLAW_MESSENGER_API_KEY` | — | **Required.** From clawmessenger.com/dashboard. |
| `CLAW_MESSENGER_SERVER_URL` | `wss://claw-messenger.onrender.com` | WebSocket URL of the Claw Messenger service. |
| `CLAW_MESSENGER_PREFERRED_SERVICE` | `iMessage` | `iMessage` / `RCS` / `SMS`. |
| `CLAW_MESSENGER_ALLOWED_USERS` | — | Comma-separated allowlist (E.164 phones or group chatIds). |
| `CLAW_MESSENGER_ALLOW_ALL_USERS` | `false` | If `true`, any sender can talk to the bot. |
| `CLAW_MESSENGER_HOME_CHANNEL` | — | Default phone or chatId for cron jobs with `deliver=claw_messenger`. |

YAML equivalent:

```yaml
gateway:
  platforms:
    claw_messenger:
      enabled: true
      extra:
        api_key: cm_live_…             # also accepts CLAW_MESSENGER_API_KEY env
        preferred_service: iMessage
        home_channel: "+15551234567"

plugins:
  enabled:
    - imessage
```

## Agent tools

| Tool | Use |
|---|---|
| `claw_messenger_create_group` | Create a new iMessage/RCS/SMS group with two or more E.164 phones and send the first message. Returns the `chat_id` to use for follow-up sends. |

Outbound DMs and replies to existing groups don't need a tool — Hermes routes them through the standard messaging flow.

## Cron delivery (out-of-process)

```yaml
cron:
  jobs:
    - name: morning-summary
      schedule: "0 9 * * 1-5"
      prompt: "Send me the day's calendar"
      deliver: claw_messenger     # → CLAW_MESSENGER_HOME_CHANNEL
```

When `hermes cron run` executes in a separate process from `hermes gateway`, the plugin's `standalone_sender_fn` opens a one-shot WebSocket connection, delivers the message, and closes. No gateway dependency.

## Development

```bash
git clone https://github.com/tin-computer/hermes-imessage.git
cd hermes-imessage
pip install -e ".[dev]"
pytest tests/                              # 45 unit tests, ~9s
```

Live smoke test against the production service (needs a real API key):

```bash
CLAW_MESSENGER_API_KEY=cm_live_… python -c "
import asyncio
from gateway.config import PlatformConfig
from hermes_claw_messenger.standalone import standalone_send
asyncio.run(standalone_send(PlatformConfig(enabled=True, extra={}),
                            '+15551234567', 'live test'))
"
```

## What this plugin does on your machine

- Keeps one authenticated WebSocket open to the Claw Messenger service (`wss://claw-messenger.onrender.com` by default) while the gateway runs, and sends and receives your messages over it. Message text, phone numbers and attachments pass through Claw Messenger, which is how they reach phones.
- Downloads inbound attachments over HTTPS into Hermes's media cache.
- Reads `CLAW_MESSENGER_*` settings through Hermes (`get_secret`). `hermes gateway setup` saves them with Hermes's own `.env` writer; settings in `config.yaml` are copied into the process environment at startup.
- Opens a short-lived connection for cron deliveries when the gateway runs in another process.
- Runs no shell commands, sends no telemetry and reads no files outside its own.

## Naming note

The catalog entry is `claw-messenger` and the PyPI package is `hermes-imessage`. The
Python module is `hermes_claw_messenger` and the Hermes platform identifier is
`claw_messenger`. All of these can appear in logs and config; they are the same plugin.

## License

MIT
