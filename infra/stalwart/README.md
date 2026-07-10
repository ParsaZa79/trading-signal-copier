# Stalwart transactional mail runbook

This directory is a reviewed design and test fixture. Nothing here deploys itself. The
production-changing commands below are operator procedures: run them only in an approved
maintenance window. This repository work must not run them against a server.

The target is Stalwart `v0.16` for low-volume transactional mail. Its permanent exposure is
deliberately narrow:

| Path | Reachability | Purpose |
| --- | --- | --- |
| TCP 25 | public host port | server-to-server SMTP, inbound and outbound |
| TCP 587 | `trading-platform-mail` only | authenticated dashboard submission with STARTTLS |
| TCP 18080 -> 8080 | host loopback, bootstrap only | initial setup UI through a tunnel |
| 80, 443, 8080 and all other mail ports | unavailable | no public or private admin listener |

`compose.yaml` contains neither `STALWART_RECOVERY_ADMIN` nor recovery mode. It has no HTTP
port and enforces the invariant `traefik.enable: false`. Never add a Dokploy domain for Stalwart and
never route the mail hostname to port 8080. The admin UI is allowed only during the one-time
loopback bootstrap; remote access must traverse an authenticated SSH tunnel over the VPN.
Run Stalwart as **standalone Docker Compose outside Dokploy** on the Docker host; only the
dashboard remains Dokploy-managed. Never create a Dokploy Stalwart application or Compose
service. This single ownership model lets every lifecycle command use the exact Compose project
`trading-platform-mail` and avoids Dokploy's generated Compose project names or a second container
competing for port 25. Never use Docker Stack mode: Swarm ingress publishing does not provide the
required `127.0.0.1` host-binding boundary.
The base also omits `STALWART_PUBLIC_URL`: this SMTP-only deployment must not advertise an HTTPS
JMAP/OAuth URL that it deliberately does not serve.

The machine-readable contracts are:

- `network-policy.yaml`: exact network driver, egress property, and membership allowlist.
- `listener-policy.json`: the only two allowed Stalwart `NetworkListener` objects.
- `tls-policy.yaml`: the primary DNS-01 certificate path and external-certificate fallback.
- `backup-policy.yaml`: schedule, consistency, retention, off-host protection, RPO and RTO.

## Dedicated mail network

`trading-platform-mail` is a dedicated attachable Swarm overlay. It is **not** an internal
network, so Stalwart retains NAT/routed egress for MX lookup, outbound SMTP, DNS-01 and other
required Internet access. Lack of `internal: true` is intentional; isolation comes from the
membership allowlist and unpublished ports.

Creating the network is a one-time, server-changing maintenance action:

```sh
docker network create \
  --driver overlay \
  --attachable \
  --label com.kiaparsa.purpose=transactional-mail \
  trading-platform-mail
```

The Stalwart compose declares it as `external: true`, so a missing network fails closed rather
than silently creating a project-scoped replacement. Start/recreate the standalone service only
with the repository's top-level Compose name and the same explicit project name used by
`bootstrap.sh`:

```sh
docker compose \
  --project-name trading-platform-mail \
  --project-directory infra/stalwart \
  --file infra/stalwart/compose.yaml \
  config --quiet

# Maintenance action after review and approval; not run by repository validation.
docker compose \
  --project-name trading-platform-mail \
  --project-directory infra/stalwart \
  --file infra/stalwart/compose.yaml \
  up -d --force-recreate stalwart
```

The explicit volume names keep data stable across lifecycle definitions. Before acting, reject
any existing Dokploy-managed Stalwart workload, any container from another Compose project using
these volumes, or any listener already occupying port 25. In Dokploy, edit only application
`lku4v_DVjO_BEJSSQgBZi` (`trading-dashboard`): under **Advanced -> Swarm Settings -> Network**,
add target `trading-platform-mail` with alias `trading-dashboard`, retain its existing
`dokploy-network`, save, preview the service spec, and redeploy only after explicit approval.
Set the application SMTP endpoint to `stalwart:587`. Do not attach `trading-api`, `mt5`, or
Traefik to this overlay.

After that maintenance, a manager-side read-only `docker network inspect
trading-platform-mail` must show only the Stalwart and dashboard tasks (plus Swarm's own
load-balancer endpoint). Reject the change if any API, MT5, Traefik, or unknown workload is a
member. Confirm `Internal=false`, `Attachable=true`, and `Driver=overlay`. From the dashboard
task, DNS for `stalwart` must resolve and TCP 587 must connect; from unrelated services it must
not. Confirm outbound TCP 25 from Stalwart separately—network isolation must not block delivery.

Dokploy's application network fields (`Target`, `Aliases`, and `DriverOpts`) are documented in
the official [application Advanced guide](https://docs.dokploy.com/docs/core/applications/advanced).

## One-time bootstrap and permanent removal

`compose.bootstrap.yaml` is a standalone maintenance definition, not a production overlay. It
uses the same two named volumes as the base, but publishes only
`127.0.0.1:18080:8080`, attaches only a project-scoped `bootstrap-admin` bridge, publishes no
SMTP port, and never joins `trading-platform-mail`. The non-internal bridge preserves outbound
DNS/ACME access without making the admin listener reachable from the dashboard. The credential
format is `username:password`; create it in a password manager and pass it through an ephemeral
shell environment without printing it. `compose.recovery.yaml` adds only
`STALWART_RECOVERY_MODE=1` to that isolated definition.

1. Confirm the external overlay and both named volumes are ready. The **server** returned by
   `docker version --format '{{.Server.Version}}'` must be 28.0.0 or newer. Docker documents that
   releases before 28.0.0 allowed neighbors on the same L2 segment to reach localhost-published
   ports. `bootstrap.sh start` parses the server version and refuses to publish the admin port on
   an older engine. Upgrade and revalidate the host firewall first; do not bypass this gate or
   substitute the client version. Also reject daemon/network modes that deliberately bypass
   Engine 28's port-filtering hardening.
2. Set `STALWART_RECOVERY_ADMIN` in an interactive maintenance shell, then explicitly run:

   ```sh
   infra/stalwart/bootstrap.sh start --confirm-maintenance
   ```

3. Tunnel to the server over the VPN, for example by forwarding local port 18080 to server
   loopback port 18080. Visit `http://127.0.0.1:18080/admin`. Do not browse to a public address.
4. Complete the v0.16 wizard and create a separate permanent administrator. Wizard completion
   writes `config.json` and restarts Stalwart into normal mode; official v0.16 behavior removes
   the bootstrap HTTP service, so the 18080 session is expected to close. Do not assume it can
   still be used for post-wizard configuration.
5. Reopen an explicit, isolated recovery window using the same ephemeral credential:

   ```sh
   infra/stalwart/bootstrap.sh recovery --confirm-maintenance
   ```

   This sets `STALWART_RECOVERY_MODE=1`, keeps public SMTP unbound, and restores only the
   loopback management API. Reopen the SSH/VPN tunnel, configure TLS and the exact listener
   policy, and confirm the permanent administrator separately.
6. **Mandatory pre-removal gate:** delete every unused configured listener, export the live
   listener objects through recovery mode, and obtain a zero exit from `verify-listeners.py`.
   Do not run the remove action without that evidence; the base recreation intentionally makes
   the management API unavailable.
7. Remove recovery/bootstrap immediately:

   ```sh
   infra/stalwart/bootstrap.sh remove --confirm-maintenance
   unset STALWART_RECOVERY_ADMIN STALWART_RECOVERY_MODE
   ```

The start/recovery actions inspect runtime network membership and the actual port binding, then
fail closed with `docker compose down --remove-orphans` if recreation partially fails, the service
is not attached only to the isolated bridge, or 8080 is not exactly `127.0.0.1:18080`. The remove
action force-recreates from the `compose.yaml` base, plus the explicit TLS-volume override only in
`--tls-mounted` mode, and inspects only environment
**names** plus a boolean for target port 8080. It fails if `STALWART_RECOVERY_ADMIN` or
`STALWART_RECOVERY_MODE` survives, or if container port 8080 still has any host binding; it never
prints a value. A failed base recreation or removal proof immediately runs `down --remove-orphans`,
leaving mail intentionally stopped instead of retaining a suspect credential-bearing container.
If that cleanup command itself fails, the script exits with a `CRITICAL` warning that the suspect
container may remain; it never claims removal without a successful Compose teardown.
Every mutating/inspection call pins Compose project `trading-platform-mail`, so an
inherited `COMPOSE_PROJECT_NAME` cannot strand a parallel bootstrap container. Treat a failed
proof as a failed cutover. After removal, connection to loopback
port 18080 must fail and the mandatory pre-removal listener snapshot must contain no HTTP
listener. Day-to-day public administration is intentionally not available. Do not retain the
bootstrap secret in Dokploy.

All three maintenance actions recreate a running service; explicit recovery mode pauses normal
mail service. The script refuses to act without the
literal `--confirm-maintenance` flag. `--help` is safe and non-mutating.

The loopback security boundary and pre-28 caveat are defined in Docker's official
[port-publishing documentation](https://docs.docker.com/engine/network/port-publishing/).
The lifecycle split is defined by Stalwart's official
[bootstrap-mode](https://stalw.art/docs/configuration/bootstrap-mode/) and
[recovery-mode](https://stalw.art/docs/configuration/recovery-mode/) contracts.

## Stalwart v0.16 listener policy

Stalwart enables several protocols during setup by default. Docker `expose` is metadata, not a
firewall, so every unused Stalwart listener must be deleted in **Settings -> Network ->
Listeners**, not merely omitted from host port mappings.

The only final `NetworkListener` objects are:

```json
{"name":"smtp","protocol":"smtp","bind":["[::]:25"],"useTls":true,"tlsImplicit":false}
{"name":"submission","protocol":"smtp","bind":["[::]:587"],"useTls":true,"tlsImplicit":false}
```

Delete HTTP/JMAP/admin, IMAP, POP3, ManageSieve and LMTP listeners, plus default listeners on
24, 80, 110, 143, 443, 465, 993, 995, 4190 and 8080. In this deployment submission uses
explicit STARTTLS on 587; port 465 is not enabled. Require authenticated submission and keep
domain `allowRelaying` false unless a separately reviewed split-delivery design needs it.

The official v0.16 CLI emits NDJSON when queried with fields. The core query is
`stalwart-cli query NetworkListener`; while the explicit recovery tunnel is active, prompt
interactively for the admin password and capture a snapshot without putting credentials in the
command line:

```sh
stalwart-cli \
  --url http://127.0.0.1:18080 \
  --user RECOVERY_USER \
  query NetworkListener \
  --fields id,name,protocol,bind,useTls,tlsImplicit \
  --json > listeners.ndjson

python3 infra/stalwart/verify-listeners.py listeners.ndjson
```

The verifier parses every object, reports all unexpected protocols/ports, checks TLS booleans,
requires exactly one listener of each name, and rejects extras. Run it before recovery removal,
after every Stalwart upgrade, and in every quarterly restore test. Keep the snapshot as a
non-secret change record.

Official contracts: [NetworkListener object](https://stalw.art/docs/ref/object/network-listener/),
[listener configuration](https://stalw.art/docs/server/listener/), and
[CLI NDJSON query output](https://stalw.art/docs/management/cli/query/).

## SMTP TLS without port 443

A certificate is not considered installed until a public STARTTLS handshake presents a trusted,
unexpired chain whose SAN covers `mail.kiaparsaprintingmoneymachine.cloud`. A self-signed
bootstrap certificate is never an acceptable production state.

### Primary: Stalwart DNS-01 with Hostinger

Use the policy in `tls-policy.yaml`:

1. In bootstrap Step 1, set server hostname to
   `mail.kiaparsaprintingmoneymachine.cloud` and enable automatic TLS.
2. In Step 5, choose automatic DNS management with provider **Hostinger** and enter a dedicated
   Hostinger API token through the secret field. Never commit, log, or paste that token into a
   command. Hostinger tokens inherit their owner's permissions, so use a dedicated operational
   identity where possible, protect the Stalwart data backup, audit use, and rotate on compromise.
3. Ensure the resulting `AcmeProvider.challengeType` is `Dns01` and the Domain references that
   provider through automatic `certificateManagement`. The default certificate for the mail
   hostname is mandatory.
4. Confirm the object relationships in the isolated recovery stage. After removing recovery and
   starting the base, wait for successful ACME issuance and DNS cleanup, then verify port 25 and
   private port 587 with `check-mail.sh`/OpenSSL before any feature flag changes.

DNS-01 writes `_acme-challenge` TXT records through Hostinger and needs no inbound 80 or 443.
Traefik may continue owning 443. Do not select HTTP-01 or TLS-ALPN-01: neither matches this port
ownership. Stalwart is pinned to the reviewed v0.16 OCI index digest
`sha256:b30c99ed8240ea42612f784babe0388318d5c3668a77873efe7e3b1147e2226e`;
do not follow mutable tag updates automatically. Upgrade only by reviewing a new digest, rerunning the
full infra suite, and repeating staging issuance. Hostinger support is present in this reviewed v0.16
image. Keep certificate-expiry and ACME-failure alerts enabled.

Official contracts: [Docker bootstrap challenge selection](https://stalw.art/docs/install/platform/docker/),
[ACME challenge types](https://stalw.art/docs/server/tls/acme/challenges/), and
[AcmeProvider fields](https://stalw.art/docs/ref/object/acme-provider/).

### Fallback: external DNS-01 and a read-only certificate volume

Use this only if the built-in Hostinger provider cannot pass a staging issuance. It is a real
certificate lifecycle, not a placeholder:

1. A separately reviewed ACME job uses lego `v4.27.0` or newer with its Hostinger DNS provider,
   a token supplied through `HOSTINGER_API_TOKEN_FILE`, and the single SAN
   `mail.kiaparsaprintingmoneymachine.cloud`. Run renewal daily and renew when no more than 30
   days remain. Use the Let's Encrypt staging directory until the full automation passes.
2. The job owns external volume `trading-platform-mail-stalwart-tls` read/write; Stalwart adds
   `compose.tls-mounted.yaml` and mounts it read-only at `/run/stalwart-tls`. The job validates
   the chain, SAN, expiry, and public-key/private-key match before atomically replacing
   `fullchain.pem` and `privkey.pem`. The final private key must be readable only by Stalwart UID
   2000 (for example owner 2000 and mode 0400); the chain may be mode 0444. Never mount the ACME
   account directory into Stalwart. Enter the isolated configuration stage with
   `bootstrap.sh recovery --confirm-maintenance --tls-mounted`; this is the only recovery variant
   that can read and validate the file-backed Certificate object.
3. Create the one-time Stalwart `Certificate` object using `certificate.manual.json`. Its fields
   use the v0.16 `File` variants and the exact in-container paths from `tls-policy.yaml`; keep the
   Domain in manual certificate-management mode. With `STALWART_URL` and `STALWART_TOKEN` supplied
   securely in the maintenance shell (never inline), capture the created ID, set the singleton
   `SystemSettings.defaultCertificateId`, and require a JSON readback match:

   ```sh
   create_output="$(
     NO_COLOR=1 stalwart-cli create Certificate \
       --file infra/stalwart/certificate.manual.json
   )"
   printf '%s\n' "$create_output"
   CERTIFICATE_ID="$(
     printf '%s\n' "$create_output" |
       sed -nE 's/^Created Certificate ([^[:space:]]+)$/\1/p'
   )"
   test -n "$CERTIFICATE_ID"
   stalwart-cli update SystemSettings --field "defaultCertificateId=${CERTIFICATE_ID}"
   stalwart-cli get SystemSettings --fields defaultCertificateId --json |
     jq -e --arg id "$CERTIFICATE_ID" '.defaultCertificateId == $id'
   ```

   This is mandatory for SMTP clients that do not send SNI; merely creating a Certificate object
   does not select it as the default. Certificate has no documented natural key, so do not turn
   this one-time `create` into an assumed idempotent upsert.
4. After initial installation or an atomic renewal, invoke the immediate reload action through an explicitly approved,
   temporary private management channel, or perform a controlled Stalwart restart if management
   is disabled by the listener policy. Close that channel immediately and re-run the listener
   verifier. Never add a permanent HTTP listener merely to make renewal convenient:

   ```sh
   stalwart-cli create Action/ReloadTlsCertificates
   stalwart-cli get Certificate "$CERTIFICATE_ID" \
     --fields id,subjectAlternativeNames,notValidAfter,issuer --json |
     jq -e --arg id "$CERTIFICATE_ID" \
       --arg host mail.kiaparsaprintingmoneymachine.cloud \
       '.id == $id and (.subjectAlternativeNames | index($host) != null)'
   ```

   A successful action invocation only means the reload was accepted; the SMTP probes below are
   the authoritative deployment postcondition.
5. Recreate the final service with
   `bootstrap.sh remove --confirm-maintenance --tls-mounted`. Omitting the flag would correctly
   remove the certificate volume and make the file paths unavailable, so the two fallback flags
   are an inseparable reviewed lifecycle choice. The removal action still proves the recovery
   environment and 8080 binding are absent.
6. Compute the expected leaf fingerprint from the newly deployed full chain in the ACME job,
   without reading or exposing the private key, then require that exact leaf on public port 25
   and from the dashboard on private port 587:

   ```sh
   EXPECTED_SHA256_FINGERPRINT="$(
     openssl x509 -in "$DEPLOYED_FULLCHAIN" -noout -fingerprint -sha256 |
       sed 's/^[^=]*=//'
   )"
   infra/stalwart/check-mail.sh --smtp-only \
     --expected-sha256-fingerprint "$EXPECTED_SHA256_FINGERPRINT"
   infra/stalwart/check-mail.sh --smtp-only --connect-host stalwart --port 587 \
     --expected-sha256-fingerprint "$EXPECTED_SHA256_FINGERPRINT"
   infra/stalwart/check-mail.sh --smtp-only --no-sni \
     --expected-sha256-fingerprint "$EXPECTED_SHA256_FINGERPRINT"
   ```

   The helper prints the trusted leaf's SHA-256 fingerprint, serial, and expiry for the renewal
   record and fails if the fingerprint is still the prior certificate. The `--no-sni` probe keeps
   hostname and trust verification enabled while proving the runtime default-certificate path.
   Alert and retain the old files if deployment, reload, or any presentation check fails.

The exact lego provider contract is documented at
[lego Hostinger DNS](https://go-acme.github.io/lego/dns/hostinger/). Stalwart's file object and
reload semantics are documented under [Certificate](https://stalw.art/docs/ref/object/certificate/),
[SystemSettings](https://stalw.art/docs/ref/object/system-settings/),
[CLI create](https://stalw.art/docs/management/cli/create/),
[CLI get](https://stalw.art/docs/management/cli/get/),
[actions](https://stalw.art/docs/management/tasks-actions/actions/), and
[TLS certificates](https://stalw.art/docs/server/tls/certificates/). The built-in primary is
preferred because it renews without reopening a management listener or restarting SMTP.

## DNS, SMTP and deliverability gate

Before any real recipient is contacted, verify against authoritative/public resolvers:

- `A mail.kiaparsaprintingmoneymachine.cloud` resolves only to the approved mail host address.
- Apex `MX` points to that fully qualified mail host and no unintended exchanger remains.
- PTR for the approved public address points back to the same mail hostname, and forward DNS
  returns that address. PTR is configured with the IP provider, not in the forward zone.
- SPF authorizes only intended senders; start with a terminating `-all` once inventory is final.
- The Stalwart-generated DKIM selector exists and a delivered signature verifies.
- DMARC has aligned SPF or DKIM, a reporting address, and starts at `p=none`; advance to
  quarantine/reject only after reports show every legitimate sender.
- CAA allows the selected ACME CA. Publish TLSA only with DNSSEC and a tested rotation process.
- Do not advertise MTA-STS until its policy is actually available over trusted HTTPS through a
  separately reviewed web path; this Stalwart compose does not serve it on 443.
- A bounce/Return-Path mailbox exists, is monitored, and does not silently discard DSNs.

`check-mail.sh` is a read-only helper. It checks A/MX/SPF/DMARC, optional PTR/DKIM, a trusted
SMTP STARTTLS hostname, emits the leaf certificate SHA-256 fingerprint/serial/expiry, can require
an exact expected fingerprint, and supports an optional RCPT-only negative relay probe. Examples:

```sh
infra/stalwart/check-mail.sh \
  --expected-ip APPROVED_PUBLIC_IP \
  --dkim-selector SELECTOR

infra/stalwart/check-mail.sh \
  --connect-host stalwart \
  --mail-host mail.kiaparsaprintingmoneymachine.cloud \
  --port 587 \
  --smtp-only
```

## Relay rejection and authenticated submission gate

Run the negative relay probe from an approved external test host:

```sh
infra/stalwart/check-mail.sh \
  --relay-recipient controlled-nonlocal-recipient@example.net
```

Run the port-587 form from the dashboard workload on the private overlay. The relay probe uses an
unrelated non-local sender, stops after `RCPT TO`, sends no DATA, and must receive a definitive
5xx rejection. A 2xx response is a cutover blocker. Also verify unauthenticated submission on
587 is rejected, AUTH is offered only after STARTTLS, and an authenticated dashboard account can
send one approved canary. SMTP credentials are application secrets, never recovery/admin
credentials and never command-line arguments.

Send controlled, low-volume canaries to accounts you own at Gmail, Outlook, and Yahoo. For each,
record the full headers and require aligned SPF/DKIM/DMARC pass, the expected TLS hop, correct
From/Return-Path, successful inbox placement or an understood classification, and a working bounce
for a deliberately invalid address. Monitor queue age/depth, 4xx retries, 5xx failures, complaint
and hard-bounce rates, disk, ACME expiry, and DNS drift. Do not send bulk or marketing mail.

## Local Mailpit

`compose.local.yaml` pins Mailpit `v1.30.0`. Its UI is bound to
`http://127.0.0.1:8025`; SMTP 1025 is exposed only inside the internal
`mailpit-local` network and is not published on the host. A containerized local sender joins that
network and uses `mailpit:1025` with no production credentials. The network is `internal: true`,
equivalent to creating a standalone local network with `--internal`, so captured development mail
cannot leave for the Internet. Do not use production recipient
addresses or copy production SMTP secrets into this compose.

Local start/stop are explicit developer actions:

```sh
docker compose -f infra/stalwart/compose.local.yaml up -d
docker compose -f infra/stalwart/compose.local.yaml down
```

Keep every product feature flag off during local and production mail validation.

## Backups, retention and restore proof

Back up both named volumes: `trading-platform-mail-stalwart-config` and
`trading-platform-mail-stalwart-data`. Configuration objects, directory data, messages, queue
state, DKIM material and—under built-in ACME—certificate/account material are not replaceable by
backing up only one volume.

The required schedule is 02:15 UTC daily (`15 2 * * *`). A backup is valid only if produced
from either a stopped Stalwart container in an approved window or an atomic storage/filesystem
snapshot; never call a live `tar` of RocksDB consistent. Record image digest/version, volume
identifiers, UTC timestamp, file manifest and checksums. Encrypt locally before upload with an
offline-held recovery recipient/key; this client-side encryption must complete before upload to
an off-host bucket/account with versioning
and Object Lock. Backup credentials must not delete/shorten locked objects and must differ from
production credentials.

Retain 7 daily, 5 weekly and 12 monthly recovery points. Configure lifecycle rules so Object
Lock never expires an object earlier than its retention class. Monitor the scheduled job, age of
last successful upload, checksum/manifest generation, remote object existence and bucket lock
status. An on-host copy is a cache, not the backup.

Perform a quarterly restore drill into a new isolated project with no host ports and no route to
production SMTP recipients. A drill passes only when:

1. The selected object is within the 24-hour RPO, decrypts from independently held key material,
   and every manifest checksum passes.
2. Both empty target volumes are restored, permissions are correct for UID 2000, and the pinned
   Stalwart version starts without repair/config errors within the 4-hour RTO.
3. Expected domains, accounts, aliases, DKIM keys, message counts and queue state match the backup
   inventory; no recovery environment name is present.
4. A fresh listener NDJSON snapshot passes `verify-listeners.py`; no HTTP/IMAP/POP3/ManageSieve/
   LMTP listener exists.
5. The certificate SAN/expiry is valid (or a staging certificate is deliberately reissued), and
   an authenticated submission delivers only to the isolated Mailpit sink.
6. The drill records start/end UTC time, selected recovery point, RPO/RTO, checksums, evidence,
   exceptions and cleanup approval. A failed criterion opens an incident and the backup is not
   reported as restorable.

Never test restore by overwriting production volumes.

## Feature flags and cutover

Mail infrastructure readiness does not authorize product exposure. Keep all current dark-launch
flags explicitly false throughout this work:

```text
STRATEGY_LAB_ENABLED=false
OPEN_SIGNUP_ENABLED=false
CODEX_BUILDER_ENABLED=false
PAPER_LIVE_ENABLED=false
PUBLIC_STRATEGY_PUBLISHING_ENABLED=false
NEXT_PUBLIC_STRATEGY_LAB_ENABLED=false
```

Do not enable signup, verification/reset email, or other user-facing mail until networking,
listener proof, a trusted SMTP certificate, DNS alignment, negative relay checks, canaries,
bounce handling, monitoring, and a passing restore drill are all recorded and independently
approved.

## Local validation

The repository-level infra runner is documented at `infra/test.sh`. Stalwart-specific checks are:

```sh
python3 -m pytest -q infra/tests/test_stalwart.py
bash -n infra/stalwart/bootstrap.sh infra/stalwart/check-mail.sh
shellcheck infra/stalwart/bootstrap.sh infra/stalwart/check-mail.sh
STALWART_RECOVERY_ADMIN=admin:compose-validation-placeholder-not-a-secret \
  docker compose \
  --project-directory infra/stalwart \
  --env-file /dev/null \
  -f infra/stalwart/compose.bootstrap.yaml \
  config --quiet
STALWART_RECOVERY_ADMIN=admin:compose-validation-placeholder-not-a-secret \
  docker compose \
  --project-directory infra/stalwart \
  --env-file /dev/null \
  -f infra/stalwart/compose.bootstrap.yaml \
  -f infra/stalwart/compose.recovery.yaml \
  config --quiet
STALWART_RECOVERY_ADMIN=admin:compose-validation-placeholder-not-a-secret \
  docker compose \
  --project-directory infra/stalwart \
  --env-file /dev/null \
  -f infra/stalwart/compose.bootstrap.yaml \
  -f infra/stalwart/compose.recovery.yaml \
  -f infra/stalwart/compose.tls-mounted.yaml \
  config --quiet
docker compose \
  --project-directory infra/stalwart \
  --env-file /dev/null \
  -f infra/stalwart/compose.local.yaml \
  config --quiet
```

These commands parse/tests local definitions only. They do not start, stop, deploy, or change a
server.
