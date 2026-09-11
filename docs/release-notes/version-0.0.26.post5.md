# Version 0.0.26.post5

## Proxbox virtual machines list search and filtering

Current backend-runtime pairing: netbox-proxbox 0.0.26.post5 <-> proxbox-api 0.0.21.post7 <-> proxmox-sdk 0.0.13 <-> netbox-sdk 0.0.10. This netbox-sdk version is proxbox-api's REST dependency only and does not provide the semantic MCP bridge.

This maintenance release ships NetBox-native search and filtering on the Proxbox virtual machines list. The page reuses `VirtualMachineFilterSet`, exposes the standard Results and Filters tabs, and keeps sync actions and pagination. The list and API views share the same proxbox-tagged queryset helper so filter behavior stays aligned.

No compatibility floor or ceiling changes in this release. NetBox `4.5.8` through official `4.7.0` GA remains supported.

| NetBox | netbox-proxbox | proxbox-api | netbox-sdk | proxmox-sdk |
|---|---|---|---|---|
| 4.5.8-4.7.0 GA | v0.0.26.post5 | v0.0.21.post7 | v0.0.10 | v0.0.13 |
