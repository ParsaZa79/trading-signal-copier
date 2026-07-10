# gVisor maintenance and rollback

The scripts pin gVisor `20260706.0`, both architecture-specific artifact
SHA-512 digests, `/usr/local/bin/runsc`, and a digest-addressed smoke image.
They add `runsc` as an opt-in runtime only; they never set Docker's default
runtime. The official minimums enforced by preflight are Linux `4.14.77` and
Docker `23.0.0`; Docker 23 is required because the transaction uses
`dockerd --validate` before every reload.

Run from the server itself with the Docker CLI's `default` context targeting exactly
`unix:///var/run/docker.sock`. The scripts reject `DOCKER_HOST`, `DOCKER_CONTEXT`, a non-default
context, or any remote/nonstandard endpoint: their systemd and filesystem operations are local,
so mixing them with a remote Docker API would invalidate every safety proof.

Both installation and rollback are explicit maintenance-window actions. First
review the non-mutating plan:

```bash
DRY_RUN=1 infra/gvisor/install.sh
DRY_RUN=1 infra/gvisor/rollback.sh --state-dir /var/lib/gvisor-docker-install/20260706.0/<timestamp>
```

For installation, keep a second root session available and run:

```bash
infra/gvisor/install.sh --confirm-maintenance
```

Before mutation, the script validates downloads and the candidate
`daemon.json`, records the default runtime, running containers and their health,
checks every typed public probe in `health-contract.json` (HTTP/TLS plus an expected response
body), and saves the original
`daemon.json`, `runsc`, and containerd shim (or an explicit absent sentinel) in
`/var/lib/gvisor-docker-install/20260706.0/<UTC timestamp>/`. The timestamp tree and
its parents are root-owned mode `0700`; a root-owned mode `0400` integrity inventory records every
state file's SHA-512, mode and ownership plus every symlink target. Manual and automatic rollback
both reject changed or incomplete evidence before restoring anything as root. The installed
`daemon.json` retains the original owner and mode, or uses root-owned `0600` when it was absent.
The script validates that root-readable installed config before reload. A reload, runtime, smoke,
default-runtime, container or endpoint failure—or handled HUP, INT or TERM—triggers an automatic
rollback attempt that validates the rollback config before reloading and rechecks health. A failed
rollback verification is reported as critical; SIGKILL, kernel failure, and host/power loss cannot
be trapped, which is why the second root session and printed manual rollback path remain required.

To perform a separately reviewed manual rollback, use exactly the state path
printed by the installer:

```bash
infra/gvisor/rollback.sh \
  --state-dir /var/lib/gvisor-docker-install/20260706.0/<timestamp> \
  --confirm-maintenance
```

Rollback restores original file modes as well as contents, including removing
files that were originally absent. It does not restart or stop Docker, stop
containers, alter volumes, or remove Docker data. A successful rollback means:

- the restored daemon configuration validated before Docker reload;
- Docker's default runtime equals its captured pre-install value;
- every container that was running before installation is still running and is
  either healthy or has no Docker healthcheck; and
- every captured public liveness probe returns a successful HTTPS response whose body matches
  its typed contract.

The API probe deliberately uses the public root identity document, not the authenticated,
MT5-dependent `/api/health/` route. Docker health status covers healthchecked containers, while
the typed API identity and stable dashboard-specific `Signal Copier` marker prove that Traefik reaches the
expected applications rather than merely returning an arbitrary 2xx or generic HTML page.

Keep the state directory and maintenance transcript as audit evidence. If
automatic rollback reports that verification failed, keep the maintenance
window open, do not delete state, and investigate from the second root session.

Official contracts used by these scripts:

- [gVisor installation and point releases](https://gvisor.dev/docs/user_guide/install/)
- [gVisor Docker runtime configuration](https://gvisor.dev/docs/user_guide/quick_start/docker/)
- [Docker daemon configuration validation](https://docs.docker.com/reference/cli/dockerd/#daemon-configuration-file)
- [Docker alternative runtime schema](https://docs.docker.com/reference/cli/dockerd/#configure-runtimes)
- [Docker Official `hello-world` image](https://hub.docker.com/_/hello-world)
