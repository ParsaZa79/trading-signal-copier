# Infrastructure verification

From the repository root, run:

```bash
./infra/test.sh
```

The command uses the committed uv locks to run the parsed Compose and mocked shell
tests, checks every infra shell script with `bash -n`, runs ShellCheck, renders the
base/standalone-bootstrap/recovery/recovery-with-mounted-TLS/local/mounted-TLS Compose variants, and verifies the API
feature flags still default to off. Compose is only rendered with `config --quiet`; it never starts containers. The
renders ignore local env files, and the bootstrap render receives a disposable
placeholder rather than a deployment credential.

Prerequisites are Bash, uv, Docker Compose v2, and Python 3.12 or newer. ShellCheck is
optional locally with an explicit skip notice; CI requires it. The same command runs in
[the infra workflow](../.github/workflows/infra.yml) for relevant pull requests and
pushes.
