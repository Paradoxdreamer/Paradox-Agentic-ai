# Privacy Policy — Paradox AI

**Template, not legal advice.** Drafted to match what this codebase
actually collects and does with data. If you're deploying this for real
users — especially in the EU/UK (GDPR), California (CCPA/CPRA), or
anywhere with data-protection law — have a lawyer adapt this, and make sure
your actual configuration (which providers are enabled, whether you added
analytics, etc.) matches what's written here.

*Last updated: [fill in when you publish this].*

## 1. What's collected

**Account data** (accounts mode only): email address, a salted/hashed
password (plaintext passwords are never stored), and an API key used to
authenticate your requests.

**Content data**: messages you send, files you upload or generate in your
workspace, and images you attach. This data is:
- Sent to whichever AI provider you selected (or that auto-routing/
  consensus mode selected) to generate a response
- Stored in your workspace on the operator's server until you delete it
- Stored in chat session memory (in-process, not on disk) until you clear
  it or the server restarts
- Included in workspace snapshots (zip checkpoints) until those are
  deleted

**Usage data**: which provider you used and roughly what it cost in
credits, logged for the credit system to function (`usage_log` table).

## 2. Third-party sharing — the important part

Any message, file, or image you submit may be transmitted to a third-party
AI provider configured on this instance. **This may include unofficial,
unverified third-party services** whose own privacy practices the operator
has not audited. Once your data leaves this server for a provider, its
retention, use, and protection are governed by that provider's own policies
— not this one. If Google sign-in is enabled, Google receives your OAuth
request per Google's own privacy policy; this app only receives your email,
name, and a Google account identifier back from that flow.

## 3. What this app does NOT do

- No advertising, no ad tracking, no selling data to third parties for
  marketing
- No payment processor integration by default — credits aren't linked to
  any real payment data unless the operator has added that separately
- No analytics/telemetry sent to the people who built this codebase —
  this is self-hosted software; the operator running it is the data
  controller, not the codebase's original author

## 4. Data retention & deletion

Workspace files, snapshots, and account records persist until deleted.
[Operator: state your actual retention policy and how a user can request
deletion — e.g. an email address or an in-app account-deletion feature,
which isn't built yet as of this version.]

## 5. Security

Passwords are hashed (PBKDF2-HMAC-SHA256, per-account salt), never stored
in plaintext. API keys act as bearer tokens — treat one as you would a
password. See this project's README for the operator-facing security notes
and their limits; no system is unhackable, and this template doesn't
promise otherwise.

## 6. Your choices

- You can request your data or its deletion by contacting the operator
  (see Terms of Service, Section 9)
- You can revoke your Google OAuth grant from your Google account
  settings independent of this app
- You can rotate your API key at any time via the app

## 7. Changes

The operator may update this policy. Material changes should be
communicated to users — [operator: define how, e.g. email or an in-app
notice, since none is automated in this version].
