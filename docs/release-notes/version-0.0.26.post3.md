# Version 0.0.26.post3

## Migration-history compatibility maintenance

Current backend-runtime pairing: netbox-proxbox 0.0.26.post3 <-> proxbox-api 0.0.21.post7 <-> proxmox-sdk 0.0.13 <-> netbox-sdk 0.0.10. This netbox-sdk version is proxbox-api's REST dependency only and does not provide the semantic MCP bridge.

This maintenance release preserves the migration-helper file history established by `0.0.26.post1` so the production package deployment guard can verify the package without treating an already-applied migration helper as modified history. It retains the `0.0.26.post2` soft-deleted VM purge page and the paired `proxbox-api 0.0.21.post7` orphan synchronization behavior.

No compatibility floor or ceiling changes in this release. NetBox `4.5.8` through official `4.7.0` GA remains supported.

| NetBox | netbox-proxbox | proxbox-api | netbox-sdk | proxmox-sdk |
|---|---|---|---|---|
| 4.5.8-4.7.0 GA | v0.0.26.post3 | v0.0.21.post7 | v0.0.10 | v0.0.13 |
