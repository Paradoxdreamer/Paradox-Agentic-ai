# Terms of Service — Paradox AI

**Template, not legal advice.** This was drafted to match what this specific
codebase actually does, so you (the person deploying it) have an accurate
starting point — not a polished, jurisdiction-checked legal document. Have
an actual lawyer review this before using it with real users, especially if
you're charging money, operating in the EU/UK/California, or handling
minors' data.

*Last updated: [fill in when you publish this]. Operator: [your name /
company — there is no "Paradox AI, Inc.", this is self-hosted software].*

## 1. What this service is

Paradox AI is a self-hosted tool that routes your messages to one or more
third-party AI backends ("providers"), which may include official APIs
(e.g. an NVIDIA-hosted model) and/or unofficial third-party proxies. **The
operator of this instance chooses which providers are configured** — see
Section 4.

## 2. Accounts

- You need an account (email/password or Google sign-in) to use this
  instance in its default multi-user configuration.
- You're responsible for keeping your API key confidential — anyone with it
  can act as you, including spending your credits.
- The operator can suspend or delete accounts at their discretion,
  including for violating Section 3.

## 3. Acceptable use

Don't use this service to:
- Generate content that's illegal where you or the operator are located
- Attempt to bypass, disable, or abuse the credit/rate-limiting system
- Attack, scan, or attempt unauthorized access to this service or the
  providers it connects to
- Upload or generate malware, or use the code-execution feature (if
  enabled) to attack other systems

## 4. Third-party providers — read this part

Every message you send may be forwarded to a third-party AI provider
configured by the operator. **Some providers configured on this instance by
default are unofficial, third-party proxies whose data handling, retention,
security, and reliability the operator has not independently verified.**
Assume anything you send to any provider may be logged, retained, or
processed by that provider under their own terms, which the operator does
not control. Don't send anything you wouldn't want a third party to see.

## 5. Credits

Credits are an internal usage-limiting mechanism, not a currency and not
connected to any payment processor by default. Unless the operator has
separately told you otherwise, buying, selling, or transferring credits
outside this app isn't supported and isn't guaranteed to mean anything.

## 6. No warranty

This service is provided "as is," without warranty of any kind. The
operator does not guarantee uptime, accuracy of AI-generated content, or
that generated code/files are safe to run without your own review — see
the code-execution safety warning in this project's README.

## 7. Limitation of liability

To the maximum extent permitted by law, the operator isn't liable for
indirect, incidental, or consequential damages arising from your use of
this service, including damages from AI-generated content or from code
executed via the Run feature.

## 8. Changes

The operator may update these terms. Continued use after a change means
you accept the update.

## 9. Contact

[operator: put a real contact method here]
