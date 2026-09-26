# SafeCircle: local demo

A scam-check companion for older adults, with a family view. The elder sends anything suspicious (a message, link or screenshot) and gets a plain-language verdict in English, Hindi or Marathi, which can also be read aloud. The family sees what the elder chooses to share.

This version runs on one computer, and a phone can open it over Wi-Fi. The detection core has no UI code in it, so the WhatsApp version will plug into the same engine later.

## Run it

You need Python 3.9 or newer. There's nothing to install.

```bash
python server.py
```

Open http://localhost:8000. The elder's phone is on the left and the family view is on the right; on a narrow screen you switch between them with tabs.

**To demo on a real phone:** run `python server.py --host 0.0.0.0` and open `http://<your-computer's-IP>:8000` on a phone on the same Wi-Fi. One caveat: browsers only allow the microphone on `localhost` or HTTPS. Over plain Wi-Fi the voice-typing button won't work, but everything else, including reading replies aloud, will.

**To turn on AI checking** (reading screenshots and catching subtler scams such as romance manipulation), copy `.env.example` to `.env` and add your Anthropic API key. Without a key, the demo runs on rules only and asks for text instead of screenshots. Use `--no-ai` to force rules-only mode even when a key is set.

To check detection quality:

```bash
python eval.py        # rules only
python eval.py --ai   # rules + AI
```

## A 5-minute demo script

1. **Family impersonation.** Tap *New number, needs money*. It's flagged as serious. Tap *Ask my family*: the alert appears in Rohan's view within a few seconds.
2. **Language and voice.** Switch to हिंदी and tap *पुलिस / डिजिटल अरेस्ट*. Tap the speaker icon to hear the verdict. Then tap *अब क्या करूँ?* for the step-by-step advice, including 1930.
3. **No false alarm.** Tap *Real bank OTP*. It isn't flagged, because it says "Do not share". Point out that the verdict says "No warning signs found", never "safe".
4. **Privacy controls.** Open ⋮ settings and switch between the three sharing levels. Watch the family view change: message text appears only under "everything I check".
5. **Community protection.** Check a scam, tap *Report this*, then send a harmless-looking message from the same phone number. It's now flagged as previously reported.

## How it works

```
text / screenshot / voice-typed message
        │
        ▼
  extract.py   links, phone numbers, UPI IDs, amounts; offline link checks
  rules.py     India scam signals (EN / HI / MR / Hinglish) → playbooks → risk floor
  llm.py       optional: reads screenshots, adds signals (fixed list, JSON only)
        │
        ▼
  engine.py    combines them: rules set a floor, the AI can raise risk but never lower it;
               low-confidence AI escalations become "be careful" plus human review
        │
        ├── replies.py   pre-written wording in three languages, never free-form AI text
        └── store.py     SQLite: cases, one alert per case, sharing settings,
                         hashed reported numbers/links; screenshots are never saved
```

| Path | What it is |
|---|---|
| `server.py` | Standard-library HTTP server and JSON API |
| `shield/` | The channel-agnostic detection core |
| `static/index.html` | The demo UI (elder chat and family view) |
| `samples.json` | Example messages used by the chips and by `eval.py` |
| `data/` | The SQLite database, created on first run; delete it to start fresh |

### API

| Method | Path | Purpose |
|---|---|---|
| POST | `/api/check` | `{text?, image? (data URL), lang}` → verdict and reply |
| POST | `/api/cases/{id}/ask-family` | Alert the family member |
| POST | `/api/cases/{id}/report` | Add the case's numbers, UPI IDs and links to the reported list |
| GET | `/api/cases/{id}/advice?lang=` | Step-by-step advice |
| GET | `/api/guardian` | Family view: stats, alerts, visible cases (masked) |
| GET/POST | `/api/settings` | Sharing level, names |
| POST | `/api/alerts/{id}/handled` | Mark an alert as handled |
| POST | `/api/reset` | Clear all demo data |

## Moving to WhatsApp later

Everything in `shield/` carries over unchanged. The WhatsApp version adds:

- **A webhook receiver** that verifies Meta's signature, deduplicates by message ID, queues the event and immediately sends a "checking…" reply.
- **A case builder** that waits about 8–10 seconds after the last forwarded item and merges them into one `engine.check()` call.
- **Media handling:** download images and voice notes from the Cloud API; send voice notes to Indic speech-to-text and images to the existing screenshot path.
- **Reply mapping:** `reply.buttons` map directly onto WhatsApp's three reply buttons, and `reply.speech` goes to text-to-speech and is sent back as an OGG/Opus voice note.
- **Family alerts:** `engine.ask_family` sends a pre-approved utility template to the family member instead of updating the dashboard.
- **Production storage:** Postgres in an Indian region instead of SQLite, plus real user accounts and linking, with the elder's consent recorded.

## Known limits of this demo

- **The samples measure only that the rules work as written.** The rules were written alongside `samples.json`, so a 15/15 score says little about real-world accuracy. Before any pilot, build a test set of real forwarded scams and ordinary messages collected from users, and track how many serious scams are missed.
- **Link checks are offline only.** A real deployment adds domain age, Google Safe Browsing and expansion of short links. The official-domain list in `extract.py` must be maintained; Indian banks are moving to `.bank.in` domains.
- **Voices depend on the device.** Reading aloud uses the browser's built-in voices. A Marathi voice isn't always installed, in which case the demo falls back to a Hindi voice.
- **Everything is local, for one elder and one family member.** There are no accounts or authentication. Don't expose the server to the internet.
- **Wording needs review.** Hindi and Marathi text should be checked by native speakers with older users before any real use.
- **1930 and cybercrime.gov.in** are the national cybercrime helpline and portal. Confirm them before launch.
