---
name: dokploy-trading-signal-copier
description: Use for Dokploy deployment inspection, troubleshooting, and safe operational guidance for the trading-signal-copier repo at /Users/parsaz/Documents/Dev/Projects/Personal/trading-signal-copier. Trigger when the user asks how this repo is deployed, asks to inspect Dokploy CLI state, debug Dokploy deployment drift, domains, mounts, app/compose config, deployment history, MT5 container wiring, or wants to deploy/redeploy this specific project.
---

# Dokploy Trading Signal Copier

## Operating Rules

- Treat Dokploy as production. Default to read-only inspection unless the user explicitly asks for an action such as deploy, redeploy, stop, start, or config change.
- Never print secrets. Redact env keys containing `PASSWORD`, `SECRET`, `TOKEN`, `KEY`, `HASH`, `LOGIN`, `API_ID`, `API_HASH`, or `SERVER`.
- Check live Dokploy state before making claims. The repo and Dokploy can drift.
- If using the stock `dokploy` CLI for detail commands returns HTTP 400, use `scripts/dokploy_read.mjs`; this repo's installed CLI version has a known GET input-wrapper mismatch for several detail endpoints.
- Before deploying, report what commit/branch will be deployed and whether local `HEAD`, `origin/main`, and Dokploy's last recorded deployment agree.

## Quick Workflow

1. Confirm repo:
   ```bash
   pwd
   git status --short
   git remote -v
   git log --oneline --max-count=8
   ```
2. Inspect Dokploy project list:
   ```bash
   dokploy project all --json
   dokploy deployment all-centralized --json
   ```
3. For sanitized app, compose, domain, mount, and deployment details, run:
   ```bash
   node .codex/skills/dokploy-trading-signal-copier/scripts/dokploy_read.mjs summary
   ```
4. Load `references/deployment-topology.md` when the user asks for the deployment architecture, known IDs, domain wiring, persistent mounts, MT5 Docker setup, or stale-deployment interpretation.
5. Verify public endpoints when relevant:
   ```bash
   curl -sS -D - https://api.kiaparsaprintingmoneymachine.cloud/api/health/ -o /tmp/tania-api-health.txt
   curl -sS -I https://dashboard.kiaparsaprintingmoneymachine.cloud
   ```

## Safe Commands

Use these without extra approval because they are read-only:

```bash
dokploy --version
dokploy project all --json
dokploy deployment all-centralized --json
node .codex/skills/dokploy-trading-signal-copier/scripts/dokploy_read.mjs summary
node .codex/skills/dokploy-trading-signal-copier/scripts/dokploy_read.mjs app trading-api
node .codex/skills/dokploy-trading-signal-copier/scripts/dokploy_read.mjs app trading-dashboard
node .codex/skills/dokploy-trading-signal-copier/scripts/dokploy_read.mjs compose mt5docker
node .codex/skills/dokploy-trading-signal-copier/scripts/dokploy_read.mjs domains
node .codex/skills/dokploy-trading-signal-copier/scripts/dokploy_read.mjs mounts
```

Do not run these unless the user clearly requests a production action:

```bash
dokploy application deploy ...
dokploy application redeploy ...
dokploy application stop ...
dokploy application start ...
dokploy compose deploy ...
dokploy compose stop ...
dokploy compose start ...
dokploy application update ...
dokploy compose update ...
```

## Known CLI Quirk

`dokploy` CLI `0.3.0` stores auth in its package-local `config.json` and talks to:

```text
<DOKPLOY_URL>/api/trpc/<endpoint>
```

Some generated read commands send:

```json
{"applicationId":"..."}
```

The server expects:

```json
{"json":{"applicationId":"..."}}
```

So commands such as `dokploy application one --applicationId ... --json`, `dokploy compose one --composeId ... --json`, and domain/mount detail calls may fail with HTTP 400. Use the helper script, which uses the expected wrapped input and redacts sensitive values.

## Reporting Guidance

When answering the user, include:

- Project/environment names and IDs when useful.
- App names, appName/container names, build stages, domains, ports, mounts, and network/MT5 relationships.
- Latest successful deployment commit and whether it matches local/current `main`.
- Live health status separately from deployment configuration.
- Any limitations, especially CLI 400s, stale deployment data, or unhealthy MT5 connectivity.

Keep secrets out of final answers.
