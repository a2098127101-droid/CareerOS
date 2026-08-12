# StepIn 2.2 Beta

**从一件简单真实的工作开始，让每次尝试、失败、修改、反馈和迁移都成为下一步教学决策的依据。**

**Start with real work. Turn every attempt, failure, revision, feedback event, and transfer into evidence for the next learning decision.**

[中文说明](README.zh-CN.md) · [架构](ARCHITECTURE.md) · [开发路线图](ROADMAP.md) · [测试状态](TEST_REPORT.md) · [Learner Agent Runtime](docs/LEARNER_AGENT_RUNTIME_v2.1.md) · [Trajectory & Calibration](docs/LEARNER_TRAJECTORY_AND_CALIBRATION_v2.2.md)

## Product definition

StepIn is for learners with little or no internship or project experience who may not yet know what real work looks like. The product does not begin with a course catalog, job assessment or a generic career-coach chat. It begins with one simple, realistic task that the learner can attempt immediately.

**开始做 → 跟着做 → 自己做 → 失败时被诊断 → 根据反馈修改 → 换场景再做 → 小任务组成项目 → 多任务叠加能力 → 把做过的事情讲出来。**

## Current production core

StepIn 2.2 is organized around **Learner Agent + Practice Runtime + Evidence/Artifact + Human Review**. The Learner Agent has independent State, Policy, Tools, Memory, Trajectory, Execution Loop, Evaluation and bounded Calibration, exposed through `/api/learner-agent/v1`.

The LLM is a language/scaffolding layer. It cannot independently select privileged tools, bypass server gates, generate the learner's final deliverable, mark capability as mastered or activate a candidate policy.

## Real Learner Trajectory

Server-side practice events become Agent observations even when the learner is not using a chat window. The trajectory covers answer saves, hint requests, failures, completions, revisions, transfer tasks, teacher feedback, Evidence decisions, project milestones, human review and Agent interventions. Short-term Memory and the long-term Trajectory are separate.

## Policy Calibration

Trajectory metrics can generate candidate policy profiles for bounded intervention timing such as ASK, HINT, EXPLAIN, REQUEST_EVIDENCE and ESCALATE. Candidate profiles require sufficient data and explicit administrator activation. Authorization, answer-leakage prevention, gates and Evidence verification are fixed safety boundaries rather than learnable policy parameters.

## Practice-first Project Library v2.2

New practice projects use the current immutable v2.2 library. A project starts from task constraints and source material, then records information processing, judgment, V1 delivery, feedback, revision, transfer, process Evidence and reflection. Existing historical projects remain bound to the template version they were created with so their evidence is not rewritten by a library upgrade.

## Production validation

Current version: `2.2.0-beta-agent-trajectory`.

StepIn 2.2 is merged into production `main` and the CI contract is locked at **204 / 204** automated tests. The production gates also include Learner Agent 13-route validation, Foundation 10-route validation, Project Library v2.2 audit, database-access audit, repository-contract audit, supply-chain security scanning and release-package boundary checks.

Engineering gates do not establish pedagogical effectiveness. Real learner trajectories and human labels are still required to calibrate educational decisions. Windows x64 install/offline/upgrade/backup-restore certification and target-environment go-live certification remain separate release gates.

## Quick start

### Windows

```text
OPEN_StepIn.cmd
```

### Python

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Local demo account settings are documented in `.env.example`. Do not enable demo seeding in production.
