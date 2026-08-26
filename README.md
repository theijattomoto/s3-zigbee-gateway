# PYGatewayListener — Technical Documentation

Package: `pyserialgateway.PYGatewayListener`
Entry point: `PYSerialGateway/pygw_main.py`

This document describes what each factorized module does and what each of
its major functions/methods is responsible for. It reflects the code as it
exists after the single-file → multi-module refactor; no logic was changed
in that refactor, only the file layout, so this documentation describes the
same behavior the original monolithic `PYGatewayListener.py` had.

---

## 1. What this program does

It runs on a Raspberry Pi / Rock 3C attached to an RF gateway node over a
USB-serial port. It:

- Listens continuously to raw ASCII packets coming off the serial port from
  streetlight nodes (heartbeat, GPS, timetable, and status packets).
- Validates, deduplicates, and timestamps those packets, then commits them
  to a PostgreSQL database.
- Actively polls the node list on a timed cycle for heartbeat and GPS data.
- Auto-detects "day-burner" lamps (reporting OFF but still drawing power)
  and issues override-OFF / reset commands back down the serial link.
- Builds a daily `.kml` map file of node GPS fixes for Google Earth.
- Forwards confirmed packets over HTTPS to an upstream server.
- Exposes a small REST API (Flask) so an external system can push
  poll/on/off/dim/software commands down to nodes.

## 2. How it's launched

```
run-service.sh
  └─ cd PYSerialGateway/ && python3 pygw_main.py [flags...]
       └─ import pyserialgateway.PYGatewayListener as running_main
          running_main.main(options_string)     # options_string = concatenated CLI flags
```

`pyserialgateway/PYGatewayListener/__init__.py` re-exports `main` from
`main.py` (`from .main import main`) so that `running_main.main(...)`
resolves. Everything else in the package is wired together via relative
imports (`from .config import ...`, `from .database_thread import
DatabaseThread`, etc.) rather than the bare module-level globals the
original single-file script relied on.

Recognised CLI flags (parsed by `config.py`, checked as substrings of the
concatenated flag string inside `main()`):

| Flag | Effect |
|---|---|
| `GPSUP` | Enables GPS node-mapping polling |
| `DBUP` | Enables daily local-CSV → PostgreSQL DB sync |
| `DEMOUP` | Disables autonomous node recovery actions (demo mode) |
| `NOPOLL` | Disables active heartbeat/GPS polling |
| `NOSELMOS` | Disables all outbound data sending to the main server |
| `NOAUTH` | Disables HTTP basic auth on outbound packets |
| `TESTUP` | Sends data only to the test server, not the main server |

## 3. Package layout

```
pyserialgateway/PYGatewayListener/
├── __init__.py             re-exports main()
├── config.py                argparse + pygw_conf + encrypted cert bundle loading + db_* settings
├── db_connection.py          get_connection() - centralized PostgreSQL connection helper
├── utils.py                   Clock, StatObjectExceptionAPI
├── database_aligner.py        DatabaseAligner
├── kml_manager.py               KMLMapManager
├── serial_manager.py            SerialObjectManager
├── rest_api.py                   RESTAPI, RESTMainControllerThread
├── http_thread.py                MainHTTPURLThread
├── record_thread.py              MainRecordThread
├── reset_thread.py               MainResetThread
├── polling_thread.py             MainPollingThread
├── gps_database_thread.py        GPSDatabaseThread
├── database_thread.py            DatabaseThread
├── recovery_thread.py            RecoveryThread
├── gps_thread.py                 GPSThread
├── timetable_thread.py           TimetableThread
├── main_listener_thread.py       MainListenerThread
└── main.py                       main() orchestration function
```

Outside the package, two config files feed `config.py` (see the updated
`config.py` reference in §6 for the full mechanism):

```
PYSerialGateway/pygw_conf.py             site-specific config for this deployment (tried first)
pyserialgateway/config_PYproperties.py   packaged template/fallback (placeholder values)
```

## 4. High-level architecture

```
                         +---------------------+ -> G0 packets --> GPSThread       -> good data --> GPSDatabaseThread -> requires action --> +--------------------+
Raw serial packets  -->  | MainListenerThread  | -> P0 packets --> TimetableThread -> ---------------------------------> requires action --> | Other Main Threads |
                         +---------------------+ -> all others --> RecoveryThread  -> good data --> DatabaseThread    -> requires action --> +--------------------+
                                                                  (Recovery Stage)                    (DB Stage)                                    (Feedback Control Action)
```

`main.py`'s `main()` function owns the serial port, spins up one
`MainListenerThread` per raw packet read, and runs a set of long-lived
"Main*" threads alongside it for polling, resets, HTTP forwarding, the
REST server, and error logging. `MainListenerThread` is the fan-out point:
depending on a packet's label it spawns a short-lived `GPSThread`,
`TimetableThread`, or `RecoveryThread`, each of which does its own
validation before optionally spawning a `DatabaseThread` or
`GPSDatabaseThread` to commit to PostgreSQL.

## 5. Threading model

| Thread | Started by | Lifetime | Purpose |
|---|---|---|---|
| `MainPollingThread` (`poll_t`) | `main()` | Long-lived | Cycles through the node list sending heartbeat/GPS/override-OFF commands |
| `MainResetThread` (`reset_t`) | `main()` | Long-lived | Drains 3 command queues (reset, REST-controller, timetable-query) to the serial port |
| `MainRecordThread` (`record_t`) | `main()` | Long-lived | Drains `record_queue`, writes faulty-packet descriptions to `error.log` |
| `RESTMainControllerThread` (`REST_t`) | `main()` | Long-lived | Runs the Flask/WSGI REST server on port 9090 |
| `MainHTTPURLThread` (`http_t`) | `main()` | Long-lived | Drains `msg_queue`, POSTs confirmed packets upstream over HTTP(S) |
| `MainListenerThread` | `main()`'s loop, once per raw packet | Short-lived, joined before next read | Splits/labels one raw packet and dispatches sub-threads |
| `GPSThread` | `MainListenerThread` | Short-lived | Validates a batch of G0 (GPS) packets |
| `TimetableThread` | `MainListenerThread` | Short-lived | Validates a batch of P0 (timetable) packets |
| `RecoveryThread` | `MainListenerThread` | Short-lived | Validates all other packet types (H1/H2/E1/E2/E4 etc.) |
| `DatabaseThread` | `RecoveryThread` | Short-lived | Commits validated packets to `filter_time_py` in PostgreSQL |
| `GPSDatabaseThread` | `GPSThread` | Short-lived | Commits a confirmed GPS fix to `node_database` in PostgreSQL |

`main()` also runs a watchdog pass every loop iteration that detects any
dead long-lived thread, clones and restarts it, and re-hands it the current
serial port object.

## 6. File-by-file reference

### `config.py`

Startup argument parsing and external configuration loading. Runs
unconditionally at import time (not wrapped in a function), so every other
module that does `from .config import X` triggers this exactly once
(Python caches the module after first import).

- **argparse setup** — defines the 7 CLI flags listed in §2 and parses them
  into `args` (a `Namespace`). Note: `args` is not actually consulted
  anywhere else in the codebase — see §8.
- **`pygw_conf` resolution** — tries `import pygw_conf` first (a file
  expected to sit next to whatever script is running, e.g.
  `PYSerialGateway/pygw_conf.py`), falling back to the packaged
  `pyserialgateway.config_PYproperties` if that's not found.
- **`location_mod`** — `pyserialgateway.__path__`, used elsewhere to locate
  `hardware_reset.py` and the encrypted `required-<codename>gw.zip` bundle.
- **`obs_instance`** — list of PIDs of other running instances of this same
  script (via `psutil.process_iter`, matching `sys.argv[0]` against each
  process's cmdline). Used to pick between `client_ID` and `client_ID_2`
  for dual-instance deployments. Guards against `cmdline` being `None`
  (some processes are not introspectable — see §8).
- **Derived config values** — reads every setting out of `pygw_conf`
  (paths, cycle/poll timing, message-ID versioning, active/inactive time
  windows, GW node identities, GPS map marker styles, cert codename) and
  computes:
  - Absolute log/DB/map paths relative to the running script's directory.
  - Minute-of-day markers (`start_marker`, `end_marker`, etc.) from the
    configured `HH:MM` time strings.
  - `between_flag` / `GPS_between_flag` / `LM_between_flag` /
    `OF_between_flag` — each encodes whether a given active window wraps
    past midnight (`0`), doesn't (`1`), or is disabled (`2`, when
    start==end). These flags gate a lot of the day/night branching logic
    in `polling_thread.py` and `recovery_thread.py`.
- **Encrypted config bundle** — opens
  `<location_mod[0]>/required-<cert_codename>gw.zip`, reads out a Fernet
  key and an encrypted payload, decrypts it, and parses a simple
  `name = { ... }` block format into `param_dict`. From that it extracts
  `full_URLstring` (upstream POST URL), `auth_key_pair` (basic-auth
  credentials + main-server auth pair), and `cert_location` (TLS client
  cert path for the main-server HTTPS leg).
- **`db_host`/`db_port`/`db_user`/`db_password`/`db_name`** — PostgreSQL
  connection settings, each read via `getattr(pygw_conf, 'db_x', default)`
  rather than direct attribute access (unlike everything else in this
  file). The defaults exactly match what used to be hardcoded in every
  `psycopg2.connect(...)` call before `db_connection.py` existed (local
  Unix socket, user `radxa`, port `5432`, database
  `serial-gateway-program`, no password), so a `pygw_conf.py` that
  predates these settings keeps working unchanged. `db_host`/`db_password`
  default to `None`, meaning "connect via local Unix socket with peer
  authentication" — set them to deploy against a remote or
  password-authenticated Postgres instead. See `db_connection.py` below
  for how these get turned into an actual connection.

### `db_connection.py`

One function: **`get_connection()`**. Builds a `psycopg2.connect(...)`
kwargs dict from `config.py`'s `db_*` settings — `host` and `password` are
only included if actually set (`None`/falsy skips them), so the default,
unconfigured case connects via the local Unix socket with peer
authentication, identical to the hardcoded calls it replaces. Every DB
call site (`database_aligner.py`, `database_thread.py`,
`gps_database_thread.py`) calls this instead of `psycopg2.connect(...)`
directly, so deploying against a different database (different OS user,
a remote host, a different database name) only requires editing
`pygw_conf.py` — no source file needs to change. Confirmed
`host=None`/omitted-`host` are behaviorally identical for `psycopg2`, so
this substitution doesn't change connection behavior for existing
deployments.

### `utils.py`

- **`Clock`** — a small stopwatch. `start()`/`stop()` toggle a running
  state; `duration` (property) returns elapsed seconds whether running or
  stopped; `__float__` and `__str__` give a millisecond/second-scaled
  numeric or human-readable duration. Used by `MainPollingThread` to time
  each polling cycle against the configured `cycle_sec` budget.
- **`StatObjectExceptionAPI`** — a generic wrapping proxy. Constructed with
  a class (`DatabaseAligner` or `KMLMapManager`), it instantiates that
  class and intercepts every method call via `__getattr__`, wrapping the
  real call in a `try/except` and mapping specific exceptions to safe
  fallback return values (e.g. `DatabaseAligner.csv_check` failures return
  `(False, 0, {}, [])`; `KMLMapManager.run`-named failures call
  `sys.exit`). This is what lets the rest of the codebase call
  `DBAligner.run(...)` / `KMLMapper.ini_run(...)` without every call site
  needing its own try/except — errors are logged and given a benign
  default instead of propagating.

### `database_aligner.py` — `DatabaseAligner`

All PostgreSQL/local-CSV alignment logic for the node list. Every DB
method opens its own connection via `db_connection.get_connection()` and
closes it in a `finally` block (i.e. no connection pooling) — previously
each of these 9 call sites had its own hardcoded
`psycopg2.connect(user='radxa', port='5432',
database='serial-gateway-program')`; now they all go through the shared
helper instead.

- **`basic_exec(*args)`** — runs an arbitrary `(query_string, data)` pair.
- **`DB_delete_node_DB(*args)`** — deletes a node row from `node_database`.
- **`DB_delete_filter_time(*args)`** — deletes a `(node, ack)` row from
  `filter_time_py`.
- **`DB_register(data, data_header)`** — upserts a node row: inserts if no
  matching `node` exists, updates non-null columns if exactly one match
  exists, or deletes-then-reinserts if more than one match exists
  (duplicate cleanup). Column list is driven dynamically by
  `data_header`.
- **`csv_check()`** — reads the local `updating_database_localpath` CSV
  (columns `pole_node, node, pan_id, channel`) into a dict keyed by node
  ID. Raises `FileNotFoundError` if the file is missing.
- **`static_read()`** — full `select * from node_database`, returns row
  count and a flat list of node IDs.
- **`final_read(port_data)`** — reads all rows matching the current
  `(pan_id, channel)`, separates auto-inserted (`TBD-AUTO`) nodes into
  `poll_exempt_nodelist`, sorts the rest numerically by hex node ID into
  `empty_nodelist`. This is the "real" active node list used everywhere
  else. Rows whose node ID isn't valid hex are deleted.
- **`select_override_OFF_list(LMactive_datetime, nodeoff_datetime)`** — the
  day-burner detector for the inactive period: for every non-exempt node,
  looks at its most recent `filter_time_py` row and decides whether it's
  currently ON outside the allowed active window, returning
  `(out_of_timerange_nodelist, empty_nodelist)` (the latter being nodes
  that need an override-OFF command).
- **`select_aggressive_poll_list(active_datetime, aggressivepoll_datetime)`**
  — during the first N minutes of the active window, finds nodes whose
  last update predates the aggressive-poll cutoff, for repeated priority
  polling; nodes over the cap are randomly down-sampled to keep the list
  bounded.
- **`dtime_active_check()`** — purges `filter_time_py` rows whose
  timestamp is in the future relative to `utcnow()` (corrupted entries).
- **`DB_timecheck(data_time_1, data_time_2)`** — simple `<` comparison
  helper.
- **`run(*args)`** — the callable entry point (`(logger, simple_logger,
  problem_logger, port_data, port_datalist, DB_check_flag)`). If
  `DB_check_flag` (the `DBUP` CLI flag) is set, reconciles the local CSV
  against PostgreSQL (insert/update/delete as needed) before re-reading.
  Always re-registers the two gateway nodes themselves (`GW-1`, `GW-2`),
  then returns the final active node list via `final_read`.

### `kml_manager.py` — `KMLMapManager`

Builds and maintains the daily `.kml` document for Google Earth.

- **`__init__`** — creates a fresh `xml.dom.minidom.Document`.
- **`add_style_to_placemark(docElement, styleID, stylehref)`** — registers
  one icon style (used for the 3 GPS marker styles: confirmed, varying,
  unconfirmed).
- **`add_placemark(node_name, node_description, node_lat, node_long)`** —
  builds one `<Placemark>` element, choosing a style URL based on the
  description tag (`#G0`, `#G0!`, `#G0-`, `#G0|V|`).
- **`writetokmlfile()`** — serializes the in-memory document to
  `self.kmlpathname`.
- **`remove_whitespace_nodes(documentFile, unlink=False)`** — recursively
  strips whitespace-only text nodes so a re-parsed document doesn't
  accumulate blank lines on every rewrite.
- **`inherit_old_document_info(kmlpathname, stylelist)`** — on startup, if
  today's KML file already exists (process restarted mid-day), re-parses
  it (once via `minidom` for the writable DOM, once via `pykml`/`lxml` to
  walk `<name>` tags) and returns the existing `<Document>` element plus
  the list of node IDs already mapped today, so they aren't remapped.
- **`ini_run(kmlpathname, stylelist)`** — cold-start path: builds the KML
  header/`<Document>`/style elements from scratch and returns the
  `<Document>` element to write placemarks into.

### `serial_manager.py` — `SerialObjectManager(serial.Serial)`

Subclasses `pyserial`'s `Serial` directly, so the object itself *is* the
open port.

- **`serial_open_gateway()`** — sets `115200 8N1`, calls `open()`, and
  takes an exclusive `flock` on the file descriptor (so a second gateway
  process can't also claim the port). Returns `False` (without raising) if
  already open or if opening/locking fails.
- **`force_close()`** — releases the flock and closes the port.
- **`gw_initial(final_ports_ind, final_ports_len)`** — sends `+DS` and
  waits (up to 5 tries) for a status reply containing `SN`, `HW`, `NodeID`,
  `PanID`, `ZM-FW`. Uses the serial number to detect whether this is a
  previously-seen port (keeps `lastportindex`) or a new one (advances it),
  then sends `+ZC<pan><channel><power>` to configure it.
- **`gateway_reset_stop2bits()`** — closes and reopens the port with 2
  stop bits (a hardware quirk used specifically to force-reset a hung
  gateway node), sends `+DR`, closes again.
- **`ini_run(*args)`** — `(logger, simple_logger, problem_logger,
  per_packet_cd, GW_datalist, lastportindex)`. Enumerates all `/dev/*USB*`
  serial ports via `serial.tools.list_ports`, sorts them by their `USBn`
  suffix, and tries each in turn: open it, run `gw_initial`; the first
  port that both opens and configures successfully is kept. Returns
  `(status, port_name, config_data, port_index)`.

### `rest_api.py` — `RESTAPI`, `RESTMainControllerThread`

**`RESTAPI`** — one Flask view method per external command, each following
the same shape: parse a `-`-delimited bundle of node IDs out of the URL
path segment, build one serial command per node, push it onto
`active_send_queue`, and return a JSON `{id, result, dtime}` response
(400 on a malformed bundle, 500 on any internal error, 200 on success).

| Method | Command prefix sent | Route |
|---|---|---|
| `pollNode` | `+PM` | `/poll-node/<nodeIdbundle>` |
| `findMeNode` | `+TFM` | `/find-me/<nodeIdbundle>` |
| `enableManualOverrideNode` | `+LM1` | `/enable-manual-override/<nodeIdbundle>` |
| `disableManualOverrideNode` | `+LM0` | `/disable-manual-override/<nodeIdbundle>` |
| `onNode` | `+LCB` | `/on-node/<nodeIdbundle>` |
| `offNode` | `+LCC` | `/off-node/<nodeIdbundle>` |
| `dimNode` | `+LCD` | `/dim-node/<nodeIdbundle>` |
| `dimlevelNode` | `+LC<level>` | `/dim-level-node/<dimLvl>/<nodeIdbundle>` |
| `softwareNode` | `#<action-codes>\|<node>\|00000`, pushed to `msg_queue` instead of the serial queue | `/software/<actionType>/<nodeIdbundle>` |

`softwareNode` maps human action names (`on`, `off`, `fault`, `cut`, `new`,
`maintenanceNo/Yes`, `pole`) to internal codes (`X1`..`Z`) via
`actionInterpreter` before building the command.

- **`ini_run(*args)`** — wires up `(logger, simple_logger,
  active_send_queue, msg_queue)`.

**`RESTMainControllerThread(threading.Thread)`**
- **`config_API()`** — registers every `RESTAPI` method against its Flask
  URL rule (manual, not auto-discovered — new endpoints must be added
  here).
- **`run()`** — starts a `wsgiserver.WSGIServer` bound to `0.0.0.0:9090`.
  Records the error class/message into `status_error_reasoning` /
  `status_error_description` on failure (consulted by `main()`'s watchdog
  to detect "port already in use" specifically).
- **`status()` / `status_error_reason()` / `clone()` / `stop()`** —
  standard watchdog-support methods (see §5 pattern below).

### `http_thread.py` — `MainHTTPURLThread`

Client thread that forwards `msg_queue` entries upstream. Always runs
(even under `NOSELMOS`) purely to drain the queue and avoid unbounded
memory growth.

- **`get_stats()` / `set_stats()`** — read/reset the daily
  `(POST count, ACK count)` pair, used by `main()` for the daily link
  quality log line.
- **`set_input_param(*args)`** — refreshes the `NOSELMOS`/`NOAUTH`/`TESTUP`
  option flags without recreating the thread.
- **`run()`** — main loop:
  1. Pulls one `(node_id, packet_data, packet_type)` from `msg_queue`.
  2. Parses the pipe-delimited raw packet fields (ack code, message ID,
     GPS satellite/HDOP if present, AC/DC electrical readings if present —
     falls back to synthetic defaults when the packet is a software-action
     packet with a shorter fixed layout).
  3. Converts the packet's UTC day/time fields into a local (GMT+8)
     timestamp string.
  4. URL-encodes the payload and POSTs it, per `self.test_align_flag` /
     `self.test_flag` (see the in-code comment table): either a single
     connection to the test-or-main server, or a dual send — always to
     `full_URLstring` (test/rest_location), and, unless `test_flag` is
     set, also to a derived HTTPS URL on the same host with a TLS client
     cert (`cert_location`) and optional basic auth
     (`auth_key_pair[2:4]`).
  5. Increments `glob_ACK_counter` on success; on `HTTPError`, `URLError`,
     `IOError` (except timeouts), or any other exception, logs and drops
     the item (`msg_queue.task_done()` either way — failed sends are not
     retried).

### `record_thread.py` — `MainRecordThread`

Simplest of the Main threads: pulls `(label_ID, description)` tuples off
`record_queue` and writes them to the problem/error logger. Exists as its
own thread specifically so that slow file I/O never blocks the
listening/recovery path — `RecoveryThread`/`TimetableThread`/`GPSThread`
just enqueue and move on.

### `reset_thread.py` — `MainResetThread`

Serializes all outbound serial *command* writes (as opposed to polling
writes, which `MainPollingThread` sends directly) from three independent
sources through one thread so they don't collide on the wire:
`TT_query_queue` (timetable fix commands), `REST_controller_queue`
(commands from the REST API), and `reset_queue` (fault-triggered resets).

- **`get_awaiting_E1_list()` / `set_awaiting_E1_list()`** — tracks node IDs
  that were reset and are expected to emit an `E1` confirmation next, part
  of the H2→E1→G0 new-node validation sequence.
- **`get_pause_status()` / `set_pause_status(new_serial_obj)`** — the
  write-side equivalent of the pause/resume pattern used across all
  serial-writing threads: a write failure sets `pause_flag = True` and
  stops consuming queues until `main()`'s port-recovery logic calls
  `set_pause_status` with a freshly reopened `SerialObjectManager`.
  Closes the old serial object before swapping in the new one.
- **`run()`** — loops each queue in priority order (`reset_G0_confirmed_
  queue` for bookkeeping only, then `TT_query_queue`, `REST_controller_
  queue`, `reset_queue`), writing each command 2–3 times with small
  delays for reliability; a write failure re-queues the message, logs it,
  releases the port lock, and sets `pause_flag`.

### `polling_thread.py` — `MainPollingThread`

The most timing-sensitive thread — a `Clock` (from `utils.py`) measures
each cycle so the thread can sleep off any slack time and keep the polling
period close to `cycle_sec`.

Key state/accessor methods (`get_pause_status`, `set_pause_status`,
`get_poll_pulse_status`/`set_poll_pulse_status`,
`get_aggressive_poll_status`, `get_GPS_varying_list`/
`get_GPS_confirmed_list`, `set_GPS_confirmed_list`/
`insert_GPS_confirmed_list`, `force_continue_loop`,
`freeze_monitor_clock`) let `main()` and other threads coordinate with the
polling cycle without touching its internals directly — see docstrings
in-code for exact semantics of each.

- **`data_snip()`** — enqueues one `+PM<nodeID>` heartbeat-poll command per
  active node (skipping poll-exempt and gateway nodes; gateway nodes are
  instead added straight to `GPS_confirmed_list` since they don't need
  polling).
- **`data_snip_GPS()`** — recomputes `GPS_poll_list` as "all active nodes
  minus nodes already GPS-confirmed today" (only when `GPS_poll_flag`,
  i.e. `GPSUP`, is set).
- **`refresh_aggressive_poll_list(active_dt, aggressivepoll_dt)`** — pulls
  the aggressive-poll candidate list from `DatabaseAligner`, enqueues the
  primary list to `polling_queue` and the overflow ("residual") list to
  `residual_polling_queue`.
- **`set_poll_list(node_list, poll_exempt_list)`** — hot-swaps the active
  node list for future cycles (doesn't disturb a cycle already in
  progress) and restarts `monitor_clock`.
- **`refresh_override_off_list(LMactive_dt, nodeoff_dt)`** — the polling
  thread's own gate around `DatabaseAligner.select_override_OFF_list`:
  only re-queries the DB once per relevant time-window transition
  (governed by `LM_between_flag`), rather than every cycle.
- **`run()`** — the main cycle, in two modes:
  - **Aggressive mode** (`aggressive_poll_ongoing_flag`): tight loop
    re-polling `refresh_aggressive_poll_list`'s output every ~`interval_
    sec/6`, interleaving one low-priority "residual" poll per node when
    available, until the list is exhausted or the flag is cleared
    externally.
  - **Normal mode**: refreshes the override-OFF list, snips the full node
    list into `polling_queue`, then for each queued node sends the
    heartbeat poll and, layered on top based on the current minute-of-day
    against `GPS_between_flag`/`LM_between_flag`/`OF_between_flag`,
    conditionally sends a GPS poll (`+TGQ`) and/or an override-OFF/wide
    OFF command (`+LM1`+`+LCC` per node, or a broadcast `+LM0FFFF` during
    the dedicated node-off window). Drains any `GPS_confirmed_queue`
    feedback into `GPS_confirmed_list`/`GPS_varying_list` as it goes. Any
    serial write failure sets `pause_flag` the same way as the other
    writer threads. At cycle end, compares elapsed time (`monitor_clock`)
    against `cycle_sec` and sleeps off the remainder, or logs a
    cycle-overrun warning if it ran long.

### `gps_database_thread.py` — `GPSDatabaseThread`

One-shot thread: given a single node's confirmed lat/long/description, it
either `UPDATE`s the existing `node_database` row (if the node is already
known) or auto-`INSERT`s a new `TBD-AUTO` row (new install detected via
GPS before it's been manually registered). Connects via
`db_connection.get_connection()`. Silently ignores update failures
specifically for `TBD-AUTO` rows (expected/benign race).

### `database_thread.py` — `DatabaseThread`

Given a batch of already-filtered packets for one label (e.g. all `H1`
packets from one listen cycle), this is the message-ID reconciliation
engine against `filter_time_py`.

- **`postgres_fetch` / `postgres_update`** — thin per-call
  connect (via `db_connection.get_connection()`) /execute/close wrappers
  (see `DatabaseAligner` for the same pattern).
- **`postgres_timecheck(data_time, packet_time)`** — returns
  `(True, delta)` if the DB's stored time is older than the packet's
  claimed time (i.e. progress), `(False, delta)` if it's newer (i.e. an
  out-of-order/late packet), or `(-1, -1)` on a parse failure.
- **`run()`** — for each node in the batch: fetches the existing
  `filter_time_py` row (if any) and compares message IDs. This is a
  rolling counter (`msgID`/`msgID_vers` config values define its format,
  `max_msgID_count` its wraparound point), so the comparison has to handle
  three cases:
  - **New node** (no existing row) → straight `INSERT`.
  - **`entry_diff == 0`** → duplicate, skip.
  - **`entry_diff > 0`** (counter moved forward normally) → update, after
    a ≥30-second debounce (skipped for `E4` packets) to avoid flooding on
    rapid re-polls.
  - **`entry_diff < 0`** → either an out-of-order/late packet (small
    negative diff) that just gets acknowledged and its `dec_count` fault
    counter bumped, or a genuine counter **rollover** (large negative diff
    near `-max_msgID_count`) which is accepted as forward progress and
    increments `rollover_count`/`miss_count` instead. Every accepted
    update also pushes `(node_ID, node_data, 0)` onto `msg_queue` so
    `MainHTTPURLThread` forwards it upstream.

### `recovery_thread.py` — `RecoveryThread`

The general-purpose packet validator for every label that isn't G0/P0
(H1/H2/E1/E2/E4 etc.) — the "Recovery Stage" in the architecture diagram.

- **`ID_filtering(nodelist, nodedatalist)`** — first pass: drops packets
  whose node ID isn't valid hex or isn't in the known node database
  (queuing a `+TRS` reset, and for genuinely new/unknown IDs seen on an
  `E1` label, an echo-location GPS poll to help identify them); also drops
  packets whose message-ID field doesn't parse. Logs everything dropped to
  `record_queue`.
- **`time_filtering(nodelist, nodedatalist)`** — the heaviest validator:
  parses the packet's embedded day/hour/minute/second timestamp field
  (with strict positional/format checks — corrupted fields are dropped and
  reset-queued), builds a `dtime` string for the DB, and applies the
  timezone offset. Then, for `H`-labelled packets only and when not in
  demo mode, cross-checks lamp override/GPS-sync state to decide whether
  to send corrective `+LM0`/`+LM1`/`+LCB`/`+LCC` commands (e.g. "GPS
  session found while lamp is still overridden → clear the override").
  Finally applies the **day-burner check**: during the active window, if
  a node reports `lamp_status == OFF` but its measured wattage is below
  `off_state_wattage` is *false* — i.e. wattage isn't actually near zero —
  it's flagged as a timetable-verification or reset candidate. Returns
  `(node_ID, node_data, msgID, dtime, override_flag, lamp_status)` tuples
  for everything that survives.
- **`packet_timecheck(earliest_time, new_time)`** — simple `<=` comparison
  helper used by `duplicate_filtering`.
- **`duplicate_filtering(nodelist, msgIDlist, dtimelist)`** — groups
  packets by `node/msgID` and keeps only one (by timestamp) per group,
  since the same message can legitimately appear more than once in one
  listen cycle.
- **`run()`** — chains the three filters above (ID → time → duplicate),
  spawns one `DatabaseThread` for the surviving batch, joins it, and logs
  each surviving packet.

### `gps_thread.py` — `GPSThread`

Validates and geocodes a batch of `#G0|...` packets.

- **`description_validation`** — trivial equality helper.
- **`raw_to_value(partpacket)`** — converts a `DDD MM.mmmm` NMEA-style
  coordinate fragment into decimal degrees.
- **`packet_data_conversion(nodeID, packet, index, condition)`** — locates
  the `N`/`S` and `E`/`W` hemisphere markers in the raw packet, extracts
  and sign-corrects latitude/longitude, and tags the result with a status
  note (`#G0` confirmed & known, `#G0-` confirmed but unknown node,
  `#G0|V|` varying/unconfirmed fix, or `#G0!` on any parse failure — with
  a fallback reference coordinate).
- **`duplicate_filtering(nodelist, labellist)`** — same group-and-keep-one
  pattern as `RecoveryThread`, keyed on `node/label` and keeping the
  earliest index per group.
- **`pinpoint_filtering(nodelist, nodedatalist)`** — classifies each
  packet as a `V` (varying, needs another cycle to confirm) or `A`
  (confirmed) fix. `V` fixes for nodes not already in `GPS_V_list` are
  deferred (logged, feedback queued, not yet mapped); everything else
  produces a `(node, label, lat, long)` tuple for mapping. Feeds
  confirm/varying state back via `GPS_confirmed_queue`.
- **`run()`** — filters the batch through `pinpoint_filtering` then
  `duplicate_filtering`, and for every node not already mapped today
  (`GPS_cfm_list`), adds a KML placemark via `kml_map_manager` and spawns
  a `GPSDatabaseThread` to persist it, then rewrites the KML file once at
  the end of the batch.

### `timetable_thread.py` — `TimetableThread`

Validates `#P0|...` timetable-configuration packets.

- **`timezone_verification(nodelist, nodedatalist)`** — first checks the
  packet's embedded time fields against `utcnow()` (>3 fields differing →
  flagged as GPS-time-not-updated, reset-queued). Then parses the
  timezone suffix (`+08` expected, found via a trailing `+` or `-`
  marker) — anything other than exactly `+08` triggers a corrective
  `+CA...` timetable-reprogram command queued to `TT_query_queue`.
- **`run()`** — logs every packet, runs `timezone_verification` (return
  value currently discarded — this thread only has side effects via the
  queues).

### `main_listener_thread.py` — `MainListenerThread`

The fan-out thread spawned once per raw packet read in `main()`'s loop
(see architecture diagram in §4).

- **`checkserialhang()`** — looks for an in-progress `+`-prefixed command
  echo in the packet; if that fragment can't be UTF-8 decoded, the node is
  considered hung.
- **`data_headerfilter()`** — finds the earliest occurrence of any known
  accepted label (`#H1|`, `#G0|`, etc.) in the raw packet and discards
  everything before it (drops leading garbage/truncated data).
- **`data_endfilter(packet_cut, verified_rawpacket)`** — recursively
  strips out any *rejected* labels that slipped through, accumulating only
  clean data into `verified_rawpacket`.
- **`packet_snipping(target_string, full_label)`** — for one label, finds
  every occurrence of that label and every packet-end marker (`#\r\n`),
  pairs them up (handling the label-count vs. end-marker-count mismatch in
  either direction), and extracts each `(node_ID, packet_slice)` pair.
- **`run()`** — orchestrates the above: hang-check (triggers a 2-stop-bit
  gateway reset and aborts this packet if hung) → header filter → end
  filter loop → per-label `packet_snipping`, dispatching each label's
  packets to a new `GPSThread` (label `G0`), `TimetableThread` (label
  `P0`), or `RecoveryThread` (everything else), then joins every spawned
  sub-thread before marking itself done.

### `main.py` — `main()`

The orchestrator. Not itself a class — one long function. Structure:

1. **Queue creation** — 9 `multiprocessing.JoinableQueue()`s, one per
   inter-thread channel (see in-code comment table for what each is for).
2. **Logger/formatter setup** — three loggers (`my_logger` — console +
   `gateway.log` info+, `my_logger_simple` — one-line `gateway.log`
   debug+, `my_logger_problem` — one-line `error.log`), each with a
   `RotatingFileHandler`.
3. **Daily time-window computation** — converts the configured
   `HH:MM` active/inactive/GPS/LM/node-off times into today's (or, per
   `between_flag`, yesterday's — for windows that span midnight)
   `datetime` objects.
4. **Object construction** — `DBAligner` and `KMLMapper` wrapped in
   `StatObjectExceptionAPI`; `SerialProcessObject` (a live
   `SerialObjectManager`); `RESTAPIObject`.
5. **Cold/warm KML start** — reuses today's existing KML file if present
   (process restarted intra-day), otherwise starts a fresh one.
6. **Serial port + node DB init** — `SerialProcessObject.ini_run(...)`
   finds and opens a port; `options_status_dict` is populated from the
   CLI flag string; `DBAligner.run(...)` loads/syncs the node list.
7. **Long-lived thread startup** — `poll_t`, `reset_t`, `record_t`,
   `REST_t`, `http_t`, each guarded by try/except: if the serial port
   isn't open (or, for polling, if `NOPOLL` was passed), the thread is
   still constructed but immediately `.stop()`ped rather than started, and
   a warning is logged — this is exactly the behavior you'll see when
   testing without hardware attached.
8. **Main loop** (`while True`):
   - **Watchdog** — checks every long-lived thread's `.status()`; a dead
     thread is cloned, restarted, and swapped back into the relevant
     local variable (`poll_t`, `reset_t`, etc.). One special case:
     if the dead thread is `RESTMainControllerThread` *and* its recorded
     error is `OSError: Address already in use`, it's logged and simply
     dropped from the watchlist instead of being cloned/restarted —
     avoiding an infinite respawn-into-the-same-conflict loop. Any other
     failure reason (for the REST thread or any other long-lived thread)
     goes through the normal clone-and-restart path.
   - **Poll-list refresh gate** — every 100 completed poll loops, triggers
     a hardware reset script (`hardware_reset.py`) via `sudo`; otherwise
     refreshes the active node list once per polling pulse.
   - **Hourly port re-check** — re-runs `gw_initial` once an hour.
   - **Daily window rollover** — advances each time window by a day (or
     within-day by an hour, for the active-window hourly stats tick) as
     `datetime.now()` crosses each threshold, toggling aggressive-poll
     mode on/off and logging HTTP link-quality stats at each transition.
   - **Daily KML rollover** — when the local date changes, starts a fresh
     `KMLMapManager` (or resumes an existing file for today, same
     cold/warm logic as startup) and swaps it in for `poll_t`.
   - **Packet read loop** — `SerialProcessObject.read_until('#\r\n ')`;
     on a read error, force-closes the port and marks it not-open. On a
     successful non-empty read, spawns and joins a `MainListenerThread`
     for that packet.
   - **Port recovery** — if the port isn't open (or `poll_t`/`reset_t`
     report a pause), constructs a new `SerialObjectManager`, re-runs
     `ini_run`, and on success re-hands it to every thread that holds a
     serial reference (`reset_t`, `poll_t`, `http_t`/`REST_t` gating
     flags) and refreshes the node/poll lists; on failure, logs "All
     serial ports cannot be opened: reconnecting..." once per second and
     retries next loop — this is the message you'll see with no hardware
     attached.

## 7. Packet lifecycle, end to end

1. `main()`'s loop calls `SerialProcessObject.read_until('#\r\n ')`.
2. A non-empty read spawns `MainListenerThread`, which header/end-filters
   the raw bytes and splits them by label into `(node_ID, packet_bytes)`
   pairs via `packet_snipping`.
3. Each label's batch goes to `GPSThread`, `TimetableThread`, or
   `RecoveryThread` depending on the label.
4. `RecoveryThread` (the common path) runs `ID_filtering` →
   `time_filtering` → `duplicate_filtering`, dropping anything invalid
   along the way (with a `+TRS` reset command queued for genuinely bad
   packets) and issuing any override-OFF/day-burner corrective commands.
5. Survivors go to a `DatabaseThread`, which reconciles the packet's
   message-ID counter against the last known value in `filter_time_py`
   and either inserts a new row or updates the existing one — handling
   normal progress, out-of-order/duplicate packets, and counter rollover
   as three separate cases.
6. Every accepted update is also pushed onto `msg_queue`, which
   `MainHTTPURLThread` drains and POSTs upstream (test server, and,
   unless `TESTUP`, the main server over HTTPS with a client cert).
7. In parallel, `MainPollingThread` independently drives the same node
   list on a fixed cycle, actively requesting heartbeat/GPS/override data
   rather than waiting for nodes to report in on their own schedule.

## 8. Notes on quirks worth knowing about

These predate the file-per-class refactor — they're called out here so
they aren't mistaken for something the split introduced.

- **`main(*args)` argument shadowing.** `main.py` defines `def main(*args)`
  and, inside it, does `options_string = ''.join(str(elements) for
  elements in args)`. The real entry point, `pygw_main.py`, calls
  `running_main.main(options_string)` — a single string — so `args` is a
  1-tuple and the join reconstructs that same string correctly. Nothing
  wrong here in the actual deployed path; it would only misbehave if
  `main()` were ever called with zero arguments.
- **`obs_instance` and `psutil`.** `config.py` guards `p.info['cmdline']`
  against `None`, which some processes return depending on OS
  permissions. Without the guard this raises `TypeError` at import time on
  environments with restricted processes (e.g. a regular desktop) even
  though it was silent on more permissive/uniform environments (e.g.
  always running as root on a Pi).
- **`return` inside `finally` in `rest_api.py`.** Every `RESTAPI` endpoint
  method ends with `finally: return json_resp`. Modern Python emits
  `SyntaxWarning: 'return' in a 'finally' block` for this because it can
  silently swallow exceptions from the `try`/`except` above it — though in
  this specific code the bare `except:` already catches everything and
  sets `json_resp` before falling into `finally`, so nothing is actually
  swallowed. Cosmetic only; not fixed as part of the refactor.
- **`pyserialgateway` is a namespace package** (no `__init__.py` at its
  own top level), which is why `pygw_main.py` needs the sibling
  `pyserialgateway/` directory to be discoverable on `sys.path` — handled
  via a `sys.path.insert` bootstrap at the top of `pygw_main.py`.

## 9. Deployment artifacts (outside the package)

These live alongside the code rather than inside
`pyserialgateway/PYGatewayListener/`, but are needed to actually run it
on a machine.

- **`PYSerialGateway/pygw_conf.py`** — the live, site-specific config for
  one deployment. This is what you actually edit per-machine: paths,
  timing windows, gateway node identities, cert codename, and (as of the
  latest changes) the `db_host`/`db_port`/`db_user`/`db_password`/
  `db_name` block. Bare `import pygw_conf` in `config.py` finds this
  because Python adds the running script's own directory
  (`PYSerialGateway/`, where `pygw_main.py` lives) to `sys.path`
  automatically.
- **`pyserialgateway/config_PYproperties.py`** — the packaged
  template/fallback, used only if `pygw_conf` can't be imported at all.
  Same fields as `pygw_conf.py`, but with placeholder values
  (`INSERTDBUSERHERE`-style) rather than working ones — this is what a
  new deployment's `pygw_conf.py` should start from.
- **`create_db.sql`** — one-time setup script for a fresh Postgres
  instance: creates the `serial-gateway-program` database and its two
  tables (`node_database`, `filter_time_py`) with column
  names/types/indexes matched directly against the queries in
  `database_aligner.py`/`database_thread.py`/`gps_database_thread.py`
  (notably: `dtime` must be `TIMESTAMP` not `TIMESTAMPTZ`, and
  `dec_count`/`rollover_count`/`miss_count` need `DEFAULT 0` — see the
  script's own comments for why). Deliberately has no `UNIQUE`/`PRIMARY
  KEY` constraint on `node` or `(node, ack)`, since `DatabaseAligner`/
  `DatabaseThread` both have branches that expect to encounter and clean
  up duplicate rows themselves; a hard constraint would turn that
  expected case into an unhandled `IntegrityError` instead. Also grants
  the configured `db_user` table/sequence privileges as its last step.
- **`pygateway.service`** — systemd unit for running this on boot with
  auto-restart. Two non-obvious settings worth knowing if this ever needs
  editing: `Restart=always` (not the more common `on-failure`) is
  required because `pygw_main.py` always exits `0` even after an internal
  crash (it catches every exception and calls `sys.exit(0)` in a
  `finally` block), so `on-failure` would never actually trigger; and
  `User=` must match whatever OS user your Postgres role/peer-auth is set
  up for, since the DB calls connect with no password by default.
- **`requirements.txt`** — the non-stdlib pip dependencies:
  `Flask`, `wsgiserver`, `psycopg2-binary`, `requests`, `pyserial`,
  `cryptography`, `psutil`, `lxml`, `pykml`.