# Africa's Talking SMS delivery investigation (2026-07-23)

## Conclusion

Africa's Talking was removed as an SMS provider for this project. Telerivet
(Android SIM route) is now the sole provider. This wasn't a quick decision —
it followed a systematic test across two live accounts, three destination
phone numbers, and multiple message formats, all converging on the same
result: messages sent through AT's shared/anonymous sender-ID pool are
consistently rejected on MTN Rwanda, and there is no configuration change
available that fixes this without a paid, telco-approved alphanumeric
sender ID.

## Background

The original project proposal specified Africa's Talking as the SMS
provider. Telerivet was added later, during initial development, after early
testing showed AT's delivery was "irregular" on MTN Rwanda — at the time,
this was treated as a reliability gap to patch with a second provider, not
a reason to remove AT outright. Both ran in parallel (`SMS_PROVIDER`
environment variable accepted a comma-separated list) until this
investigation.

The trigger for re-investigating: a live end-to-end test showed AT's API
reporting `"Success"` for a dispatched alert, but the message never reached
the test device. This prompted a full, structured re-test rather than
continuing to assume AT was "mostly working."

## What was tested

| Variable | Values tested | Result |
|---|---|---|
| Africa's Talking account | Project's own live account (`landslide`), a second live account (`lmurayire`) | Rejected on both |
| Destination phone number | 3 different Rwandan (MTN) numbers | Rejected on all 3 |
| Sender ID | Blank (AT auto-assigns the shared-pool label `AFRICASTKNG`) | Accepted by AT, but message still rejected downstream |
| Sender ID | Explicit `AFRICASTKNG` (attempting to request the shared-pool label directly) | Hard API rejection: `InvalidSenderId` — confirms this label can only be auto-assigned, never requested |
| Message format | Short plain test text | API reports `Sent`, but never delivered |
| Message format | Full alert format (`LSEWS WATCH ... Reply YES/NO ...`) | `Rejected` on AT's own delivery log |
| Message content (exact match) | The byte-for-byte identical text of a message that had **successfully delivered** via the same account and number four months earlier (2026-03-07) | **Also rejected**, sent today (2026-07-23) |

That last row is the most important data point: identical content, identical
account, identical destination number — succeeded in March, rejected in
July. That rules out message content, the specific account, and the
destination number as the cause. The only variable that changed is time,
which points to Africa's Talking's or MTN's shared-pool filtering rules
having tightened between March and July 2026 — a carrier-side policy
change, not anything configurable from this project's side.

## What "Success" / "Sent" actually means on Africa's Talking

Worth noting explicitly, since it caused real confusion during testing:
AT's API returning `{"status": "Success"}` (or the dashboard showing
`Sent`) only means AT accepted the message and forwarded it toward the
destination carrier. It is **not** a delivery confirmation — several
messages in this investigation showed `Sent` from the API and then
`Rejected` on AT's own dashboard moments later, and some `Sent` messages
never reached the test device with no `Rejected` status ever appearing.
The only way to know whether a message actually delivered is checking the
recipient's phone directly, or, if available, a genuine `Delivered` status
from the carrier — `Sent`/`Success` alone proves nothing.

## Why this can't be fixed by configuration alone

Africa's Talking requires a **registered, telco-approved alphanumeric
sender ID** for reliable delivery outside the shared pool. That's a formal
process: register the ID with AT, AT submits it to MTN/Airtel for approval,
which costs money and takes time. There is no code or `.env` change that
substitutes for this — the shared pool is what every account gets without
it, and the shared pool is exactly what this investigation found unreliable
on MTN Rwanda right now.

## What changed in the codebase as a result

- `backend/app/services/sms.py`: removed `_send_via_africastalking()`,
  `_init_at()`, `_patch_requests_ssl()`, and the `africastalking` import.
  `_dispatch_sms()` simplified to call Telerivet only.
- `backend/app/config.py`: removed `sms_provider`, `at_username`,
  `at_api_key`, `at_sender_id` fields.
- `backend/requirements.txt`: removed the `africastalking` package.
- `render.yaml`: removed `AT_USERNAME`/`AT_API_KEY`/`AT_SENDER_ID`; added
  `TELERIVET_API_KEY`/`TELERIVET_PROJECT_ID`/`TELERIVET_ROUTE_ID`, which had
  never actually been declared in the file despite being the real provider
  in use.
- `frontend/src/components/AlertPreview.jsx`: deleted — an unused,
  AT-specific component with no remaining references anywhere in the app.
- `README.md`, `help_content.py`, `HelpChat.jsx`, `.env.example`,
  `scripts/seed_demo.py`, `models/alert.py`: updated every remaining
  description of "dual provider" / "Africa's Talking + Telerivet in
  parallel" to reflect Telerivet as the sole provider.

`AlertRecord.provider_status` / `provider_errors` were kept as
`dict[str, str]` (not flattened to single fields) even though there's only
one provider now, so the frontend's existing per-provider rendering
(`AlertTable.jsx`) doesn't need to change, and a second provider could be
reintroduced later without a schema migration.
