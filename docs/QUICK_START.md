# StepIn Quick Start

## Windows local application

Double-click `OPEN_StepIn.cmd`. The launcher creates or repairs the local Python environment when needed and then starts the current StepIn desktop/runtime entry point.

`OPEN_CareerOS.cmd` and `CareerOS_H5_Showcase.html` remain compatibility identifiers for older local shortcuts and fallback paths; new instructions should use StepIn naming.

## Python development

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

## First product path

Use the current beginner-first StepIn flow: Foundation → simple real task → bounded Learner Agent support → revision → transfer → Evidence/Artifact → current Project Library v2.2 project. Do not use legacy career-planning-first templates as the default onboarding path.

Local demo account configuration is documented in `.env.example`. Do not enable demo seeding in production.
