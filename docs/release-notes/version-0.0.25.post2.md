# Version 0.0.25.post2

## Exact NetBox 4.7.0 GA compatibility ceiling

Current backend-runtime pairing: netbox-proxbox 0.0.25.post2 <-> proxbox-api 0.0.20 <-> proxmox-sdk 0.0.13 <-> netbox-sdk 0.0.10. This netbox-sdk version is proxbox-api's REST dependency only and does not provide the semantic MCP bridge.

- Keeps the Emerson-owned Proxbox plugin backward-compatible with NetBox
  `4.5.8` through `4.6.x`.
- Caps certified NetBox 4.7 admission at exact official `4.7.0` GA until a
  later patch release receives separate source, Docker, migration, and runtime
  certification.
- Synchronizes the v5 compatibility contract used by the Emerson-owned
  Proxbox-family plugins.
- Retains the normal migration and registration checks required for an easy
  upgrade from the previous post release.

| NetBox | netbox-proxbox | proxbox-api | netbox-sdk | proxmox-sdk |
|---|---|---|---|---|
| 4.5.8-4.7.0 GA | v0.0.25.post2 | v0.0.20 | v0.0.10 | v0.0.13 |
