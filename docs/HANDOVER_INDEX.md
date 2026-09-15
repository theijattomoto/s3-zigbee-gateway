# S3 Zigbee Gateway — Handover Index

## Handover scope

This handover separates gateway ownership into two operational roles.

| Team | Primary responsibility |
|---|---|
| Project Team | Operate an installed gateway and manage site configuration/node inventory. |
| Production Team | Build, provision, validate and deliver a new/replacement gateway. |
| IoT / Development | Application changes, defects, protocol/backend changes and future enhancements. |

## Project Team document

Use:

```text
docs/HANDOVER_PROJECT_TEAM_OPERATIONS.md
```

Project Team responsibilities:

- check/start/stop/restart the gateway;
- manage the complete site node list;
- manage approved PAN/channel configuration;
- apply changes using `sudo s3-gateway-dbup`;
- inspect gateway/MQTT/error logs;
- retrieve GPS KML output;
- perform basic service, USB and connectivity checks;
- escalate software defects or protected-runtime issues.

Normal operator workspace:

```text
/home/pi/S3Gateway/
```

## Production Team document

Use:

```text
docs/HANDOVER_PRODUCTION_TEAM_BUILD.md
```

Production Team responsibilities:

- install approved Raspberry Pi OS;
- install required packages and PostgreSQL;
- prepare the `s3gw` service account;
- obtain the approved source revision;
- create the production Python environment;
- prepare `/opt/s3-gateway/app`;
- configure `.env` and approved site files;
- install/enable the gateway service;
- run the approved production deployment path;
- install log retention and runtime hardening;
- initialize the site DB using the supported DBUP path;
- validate USB, MQTT, GPSUP and reboot recovery;
- deliver the completed unit to the Project Team.

## Handover validation

Run the read-only validation script on the completed production gateway:

```bash
cd ~/gateway-test/s3-zigbee-gateway
sudo bash scripts/validate-handover.sh
```

The script checks:

- service enabled/active;
- `s3gw` + `GPSUP` process state;
- operator workspace;
- GPS path/write access;
- runtime file protection;
- restricted hardware-reset sudo permission;
- PostgreSQL connectivity/tables/node count;
- log-maintenance timer;
- CP210x/ttyUSB detection;
- recent MQTT connection evidence.

Acceptance target:

```text
HANDOVER RESULT: PASS
```

`PASS WITH WARNINGS` may be reviewed and accepted only when the warning is understood and documented. Any `FAIL` must be resolved before handover.

## Project Team acceptance checklist

- [ ] Can check gateway service status.
- [ ] Can restart the gateway and verify recovery.
- [ ] Can identify the active `GPSUP` process.
- [ ] Can edit the approved operator node list.
- [ ] Can identify/edit approved PAN/channel configuration.
- [ ] Can run `sudo s3-gateway-dbup` safely.
- [ ] Can verify node counts after DBUP.
- [ ] Can inspect gateway, MQTT and error logs.
- [ ] Can retrieve GPS KML files.
- [ ] Understands protected paths and escalation criteria.

## Production Team acceptance checklist

- [ ] Can prepare a gateway from approved Raspberry Pi OS.
- [ ] Can install required system packages.
- [ ] Can prepare PostgreSQL and the `s3gw` service account.
- [ ] Can obtain and record the approved Git revision.
- [ ] Can create the production `.venv`.
- [ ] Can configure production `.env` securely.
- [ ] Can install site configuration and node inventory.
- [ ] Can install/enable the gateway systemd service.
- [ ] Can execute `deploy-production.sh` successfully.
- [ ] Can install/verify log retention.
- [ ] Can initialize the site DB using `s3-gateway-dbup`.
- [ ] Can detect the Zigbee USB gateway.
- [ ] Can validate MQTT/GPSUP/runtime hardening.
- [ ] Can perform a controlled reboot and verify automatic recovery.
- [ ] Can deliver the operator workspace to the Project Team.

## Frozen future work

The following are deliberately deferred and must not block the current handover:

- simultaneous two-USB/two-channel operation;
- multi-instance gateway service architecture;
- USB-specific hardware-reset isolation for multi-channel operation;
- new set-timetable/set-active-profile APIs;
- new MQTT command/control behavior;
- database schema redesign;
- Zigbee protocol/firmware redesign.

## Source baseline

The handover implementation was created from the proven production baseline:

```text
feature/daily-log-retention
```

Production must always use the approved branch/tag/commit supplied for the actual build; do not assume the branch name alone is sufficient release control.
