# Hardened MT5 RPyC bridge

This image pins the upstream MT5/VNC image by OCI digest and installs the
hash-verified RPyC 6.0.2 wheel into the Windows Python environment used by the
Wine RPyC server. The exact-match startup patch also pins Linux
`mt5linux==0.1.9` and fails closed if either interpreter does not report the
expected bridge versions.

## Security boundary

RPyC Classic exposes remote Python execution by design. It has no application
authentication or TLS in this deployment and must **never** be published on a
public interface. Production exposes port 8001 only to the private container
network. The local compose binds it to loopback only. A firewall/private network
is mandatory; if cross-host access is ever required, place a mutually
authenticated TLS tunnel in front of it rather than publishing RPyC Classic.

## Local validation

```bash
export MT5_VNC_PASSWORD='local-only-value'
docker compose -f mt5/compose.local.yaml up -d --build
uv run --project api python mt5/smoke-rpyc.py
```

The smoke performs only `import`, version evaluation, and read-only
`mt5.terminal_info()`. It does not log in, place orders, or call
`mt5.shutdown()`.

## Production

Create and validate the dedicated, internal, attachable network once on the
Dokploy host, before either deployment:

```bash
sudo ./mt5/ensure-production-network.sh
```

In Dokploy, open the API application's **Advanced > Networks**, attach exactly
the external network `trading-mt5-api`, and redeploy the API. Do not attach MT5
to `dokploy-network`, and do not attach the dashboard, database, or any other
service to `trading-mt5-api`. Set the API's MT5 host/URL to `mt5:8001`. Then
deploy `mt5/compose.yaml`; there is intentionally no host publication for 8001.
Keep the VNC listener loopback-bound and access it through an authenticated
administrative tunnel.

The external network survives Compose/Dokploy redeploys. The explicitly named
volume `trading-mt5-config` likewise survives container recreation; never use
`docker compose down -v`. Before migration, record rollback identifiers and
back up the volume:

```bash
docker inspect mt5 --format '{{.Image}}' > mt5.previous-image-id
docker image inspect trading-platform/mt5-rpyc:6.0.2 --format '{{.Id}}' > mt5.release-image-id
docker run --rm -v trading-mt5-config:/config:ro -v "$PWD":/backup alpine \
  tar czf /backup/mt5-config.pre-6.0.2.tgz -C /config .
```

Promotion criteria: Compose config shows only `trading-mt5-api`, RPyC has no
published host port, the image ID equals `mt5.release-image-id`, the RPyC smoke
passes with server `6.0.2`, and the expected MT5 account/config remains after a
forced container recreate. Roll back on any failed criterion: stop/remove the
new container, recreate the prior image recorded in `mt5.previous-image-id`,
and restore `mt5-config.pre-6.0.2.tgz` only if persistence validation shows the
volume changed. Never remove the external network during rollback.
