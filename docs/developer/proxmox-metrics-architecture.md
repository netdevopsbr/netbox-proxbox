# Proxmox Metrics Architecture

The metrics surface is owned by `netbox-proxbox` and `proxbox-api`. It has no
runtime dependency on another monitoring or orchestration service.

## Responsibilities

`netbox-proxbox` owns the `ProxmoxMetricsInfluxDB` mapping, persisted source
policy, encrypted InfluxDB query token, permissions, normalization,
reconciliation, and operator UI. `source_mode` is one of:

- `influx`: query only the configured InfluxDB v2 endpoint.
- `pull`: query only the mapping's `ProxmoxEndpoint` through the fixed Proxmox
  `cluster/metrics/export` operation. InfluxDB settings and a token are not
  required.
- `reconciled`: query both providers and merge their samples.

`proxbox-api` owns both typed transports. The InfluxDB route builds Flux from
bounded structured fields; arbitrary caller-supplied Flux is not accepted. The pull route resolves one
known NetBox endpoint and calls only `cluster/metrics/export`; callers cannot
supply a Proxmox API path. Both routes bound filters, rows, response bytes, and
time values and return secret-safe failures.

The browser calls only NetBox:

```text
NetBox UI or plugin API
        │  mapping id + bounded filters
        ▼
netbox-proxbox ──► persisted source policy ──► proxbox-api
                         │                         ├──► InfluxDB v2
                         │                         └──► Proxmox metrics export
                         └── normalize and reconcile results
```

## Canonical samples and reconciliation

Every provider row becomes a canonical sample with `object_id`, `metric`,
`timestamp`, `value`, `metric_type`, and source metadata. The identity key is
`(object_id, metric, timestamp)`.

Proxmox's InfluxDB writer stores pvestatd field names and object tags. The
normalizer maps official tags such as `object=qemu,vmid=101` to `qemu/101` and
field names such as `diskread`, `mem`, and `netin` to the pull API names
`disk_read`, `mem_used`, and `net_in`. Pull rows already use canonical names.

Exact cross-source duplicates collapse into one row and retain
`also_seen_in`. If equal identities contain different values, the InfluxDB row
wins and `conflict=true`; `conflict_count` reports the total. Results are sorted
by timestamp, object, and metric before the requested row limit is applied.

In `reconciled` mode, one provider may fail while the other succeeds. The
response then sets `partial=true` and reports each attempt in `source_status`.
The request fails only when every required source fails. Aggregation is rejected
when pull data participates because an Influx aggregate and a raw Proxmox
sample do not have equivalent identities.

Canonical field filters expand to every official Influx alias and one pull
metric name. Pull data has no arbitrary tag dimensions or guest-to-node
relationship, so tag filters and combined node-plus-VM filters are rejected
when pull participates. A node filter in pull modes selects that node object's
metrics.

## Failure and security boundaries

- Disabled mappings, disabled Proxmox endpoints, missing backend endpoints,
  and unusable required credentials fail closed.
- The plugin decrypts an InfluxDB token only when the persisted source policy
  includes InfluxDB. Pull-only queries never read it.
- The browser receives neither provider credentials nor connection parameters.
- InfluxDB destinations are HTTPS-only, SSRF-validated, DNS-pinned, redirect
  free, and independent of proxy environment variables.
- The pull transport selects a configured endpoint by its exact NetBox primary key and
  uses the existing authenticated Proxmox session resolver.
- Raw provider bodies and exception text are not returned to callers.

## API and UI surfaces

Metadata CRUD remains at `/api/plugins/proxbox/metrics-influxdb/`. Live data is
retrieved with `GET /api/plugins/proxbox/metrics-influxdb/{id}/data/` and
bounded query parameters. The response preserves `columns`, `rows`,
`row_count`, `truncated`, `query_window`, `captured_at`, and `response_format`
while adding reconciliation and source metadata.

## Verification evidence

Focused tests cover the official Proxmox Influx tag and field mappings, source
selection, pull-only credential isolation, fixed endpoint routing, relative
time conversion, deterministic duplicate collapse and conflict precedence,
partial-source behavior, bounds, authentication, secret-safe failures, and the
absence of arbitrary Flux and Proxmox path inputs. Release review records the
configured cyclomatic-complexity analyzer and per-function results for changed
executable code.
