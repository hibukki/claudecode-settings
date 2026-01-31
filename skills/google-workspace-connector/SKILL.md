---
name: google-workspace
description: Access Google Workspace APIs (Gmail, Drive, Sheets, Docs) via oauth2l + curl.
allowed-tools:
  - Bash
---

# Google Workspace Skill

Access Google Workspace APIs via `oauth2l` + `curl`. For extended API documentation, use context7 to query the relevant Google API docs.

## Prerequisites

**oauth2l** - Check: `which oauth2l` | Install: `brew install oauth2l`

**Credentials** - Must exist at `~/.claude/google-workspace-credentials.json`

If credentials are missing, guide user through setup. Claude can assist with browser-based OAuth setup if the user installs the [Claude for Chrome extension](https://chromewebstore.google.com/publisher/anthropic/u308d63ea0533efcf7ba778ad42da7390) in a Chrome profile where the relevant Google account is signed in (avoid having other accounts signed into the same profile).

1. **Create Google Cloud Project**: https://console.cloud.google.com/
2. **Enable APIs**: APIs & Services → Enable APIs → Enable the APIs you need (Gmail, Drive, Sheets, Docs)
3. **Configure OAuth Consent Screen**: APIs & Services → OAuth consent screen
   - User Type: External (or Internal for Workspace)
   - Add test users if in testing mode
4. **Create OAuth Client ID**: APIs & Services → Credentials → Create Credentials → OAuth client ID
   - Application type: Desktop app
   - Download JSON credentials to `~/.claude/google-workspace-credentials.json`

**First-time auth** (prints URL to click/paste in correct browser profile):
```bash
oauth2l fetch --credentials ~/.claude/google-workspace-credentials.json --scope gmail.modify --output_format bare --disableAutoOpenConsentPage
```

---

# Gmail

## List emails

```bash
curl -s "https://gmail.googleapis.com/gmail/v1/users/me/messages?maxResults=10" \
  -H "Authorization: Bearer $(oauth2l fetch --credentials ~/.claude/google-workspace-credentials.json --scope gmail.modify --output_format bare --refresh)"
```

Returns message IDs. Use `maxResults` parameter to control count.

## Read email

```bash
MSG_ID="<message_id>"
curl -s "https://gmail.googleapis.com/gmail/v1/users/me/messages/${MSG_ID}?format=metadata" \
  -H "Authorization: Bearer $(oauth2l fetch --credentials ~/.claude/google-workspace-credentials.json --scope gmail.modify --output_format bare --refresh)"
```

- `format=metadata` - Headers only (From, To, Subject, Date)
- `format=full` - Complete email including body

## Send email

```bash
EMAIL=$(printf 'To: recipient@example.com\r\nSubject: Subject here\r\nContent-Type: text/plain; charset="UTF-8"\r\n\r\nEmail body here' | base64 | tr '+/' '-_' | tr -d '=')

curl -s -X POST "https://gmail.googleapis.com/gmail/v1/users/me/messages/send" \
  -H "Authorization: Bearer $(oauth2l fetch --credentials ~/.claude/google-workspace-credentials.json --scope gmail.modify --output_format bare --refresh)" \
  -H "Content-Type: application/json" \
  -d "{\"raw\": \"${EMAIL}\"}"
```

The email must be base64url encoded (standard base64 with `+/` replaced by `-_`, padding removed).

## Additional API usage

For operations beyond list/read/send (labels, search with queries, drafts, batch operations), use context7 to query Gmail API documentation.
