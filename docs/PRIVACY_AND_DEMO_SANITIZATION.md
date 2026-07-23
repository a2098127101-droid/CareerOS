# Privacy and Demo Sanitization

## Demo policy

The default Showcase uses generic personas and a generic demo organization. It must contain no real user identity, institution, academic major, research history, API key or production record.

## Production privacy rules

- Do not use user data for model training without explicit authorization.
- Minimize personal data sent to external model providers.
- Keep tenant data isolated server-side.
- Do not mix one user’s Evidence into another user’s prompt.
- Use private object storage and authorization for uploaded files.
- Keep secrets server-side.

## Evidence separation

Maintain strict separation between:

- User Evidence
- Advisor Guidance
- External Knowledge
- Structured Job Facts

An external requirement or example must never be converted automatically into a claim about the current user.
