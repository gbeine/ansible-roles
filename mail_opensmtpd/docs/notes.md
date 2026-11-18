The role runs [OpenSMTPD](https://www.opensmtpd.org/) 7.8.0p0 in the container image `c0d3.sh/container/opensmtpd`,
based on baseimage-alpine of linuxserver.io with the package `opensmtpd` of Alpine.
The home directory of the role is mounted as `/config`, the image starts `smtpd -d -f /config/smtpd.conf`.
The init of baseimage-alpine hands `/config` over to its user `abc` at the start, the role only creates the directory and manages its content.

| Path in the home directory | Content |
|---|---|
| `smtpd.conf` | the configuration written from `opensmtpd_config`, mode `0644` |
| `tls/fullchain.pem`, `tls/privkey.pem` | the certificate of the realm of `opensmtpd_tls`, copied by `ExecStartPre` on every start, `0644` and `0600`, owned by root |
| `secrets` | an empty file, the mount point of the secret |
| `spool` | the queue of OpenSMTPD, created by the image owned by root with `0711` (`/var/spool/smtpd` links to it) |

### Configuration

`opensmtpd_config` contains the statements of [smtpd.conf](https://man.openbsd.org/smtpd.conf), merged recursively over the default of the role:

| Value | Written as |
|---|---|
| String or number | `<statement> <value>` |
| List | one line per element, the order of `match` is the order of the list |
| `true` | the statement alone |
| `null` or `false` | the statement is removed |
| Dictionary (`ca`, `pki`, `proc`, `table`, `filter`, `action`) | `<statement> "<name>" <value>` per name, a list writes one line per element |

The statements are written in a fixed order: `bounce`, `admd`, `ca`, `mda`, `mta`, `pki`, `proc`, `queue`, `scheduler`, `smtp`, `srs`,
`table`, `filter`, `listen`, `action`, `match`, so every definition comes before its use.
Lists replace the list of the default, the names of the dictionaries are merged, `null` removes a name of the default.
`include` and macros are not supported, the values are written as they are.

The default accepts mails on port 25 and only relays the mails of the container itself:

```
listen on 0.0.0.0
action "relay" relay
match from local for any action "relay"
```

An MX for a domain with submission for authenticated users:

```yaml
opensmtpd_tls:
  realm: 'mx.example.org'
opensmtpd_secrets:
  - name: 'opensmtpd'
    data: "{{ vault_opensmtpd_users }}"
    target: 'secrets'
opensmtpd_config:
  table:
    domains: 'file:/etc/smtpd/domains'
  listen:
    - 'on 0.0.0.0 tls pki mx.example.org'
    - 'on 0.0.0.0 port 587 tls-require pki mx.example.org auth <secrets>'
  action:
    relay: ~
    inbound: 'relay host smtp://mailstore.example.org'
    outbound: 'relay'
  match:
    - 'from any for domain "example.org" action "inbound"'
    - 'from auth for any action "outbound"'
opensmtpd_container:
  publish: [ '25:25', '[::]:25:25', '587:587', '[::]:587:587' ]
```

`opensmtpd_container.publish` replaces the published ports of the default (`25`), other listeners need their ports there.

### TLS

`opensmtpd_tls.realm` is the name of a realm on the host, `opensmtpd_tls.dir` the directory containing the realm.
`dir` defaults to the realms of `common_globals` (`site_pki_realms_dir`, default `/etc/pki/realms`) deployed by `pki_easyrsa_deploy`.
`ExecStartPre` of the quadlet unit copies `fullchain.pem` and `privkey.pem` of `<dir>/<realm>` with `install` to `tls/` of the home directory
on every start of the container, the role writes

```
pki "<realm>" cert "/config/tls/fullchain.pem"
pki "<realm>" key "/config/tls/privkey.pem"
```

A certificate of `pki_certbot` is in `live` of its configuration, with the same names:

```yaml
opensmtpd_tls:
  realm: 'mx.example.org'
  dir: '/opt/certbot/etc/live'
```

The files of the realm may be links (e.g. to `archive` of certbot), the copies contain the files they point to.
The listeners use it with `pki <realm>`. OpenSMTPD reads the key only owned by root with at most `0740`,
the realm is not mounted: the image changes the mode of `/config/tls/privkey.pem`, a mounted realm would lose the group `ssl-cert`,
and the links of certbot point outside of a mounted directory.
A renewed certificate is used after the next restart of OpenSMTPD: the timer of `pki_update` restarts OpenSMTPD if `fullchain.pem` of the realm
is newer than the start of OpenSMTPD, every four hours by default (`opensmtpd_pki_update_schedule`), `opensmtpd_pki_update_enabled: false` disables it.
A changed realm or `dir` changes the quadlet unit and restarts OpenSMTPD.

### Secrets

`opensmtpd_secrets` contains one secret with the target `secrets`: a table of OpenSMTPD, e.g. users with encrypted passwords
for `auth <secrets>` (`smtpctl encrypt`) or labels with `user:password` for `relay host … auth <secrets>`, see [table(5)](https://man.openbsd.org/table.5).
The secret is a podman secret mounted as `/config/secrets` with `uid=0,gid=100,mode=0440`, the role writes

```
table "secrets" file:/config/secrets
```

The image expects the table as `/config/secrets`, a file in the home directory would contain the passwords in plain text on the host,
the role only creates an empty file there as mount point.
`lka` of OpenSMTPD opens the tables after dropping its privileges to the user `smtpd` (uid 101, gid 100 in the image), so the group needs to read it.
The init script of the image changes the group to `_smtpd`, which does not exist in the image, and the mode of the mount to `0640`,
root stays the owner and only the group `smtpd` reads the table.
A changed secret restarts OpenSMTPD.

### Allowed variables

The role only allows the statements of the grammar of OpenSMTPD 7.8.0p0 (`mail_opensmtpd__config_allowed`) in `opensmtpd_config`,
the target `secrets` in `opensmtpd_secrets` and `TZ`, `PUID`, `PGID` and `UMASK` of baseimage-alpine in the environment.
The lists prevent unexpected behavior by accident, e.g. by a typo in a statement or an `include` of a file outside of the configuration.

### Container

| Variable of `opensmtpd_container` | Default |
|---|---|
| `publish` | `25:25`, `[::]:25:25` |
| `volumes` | `<opensmtpd_home>:/config` |
| `secrets` | the secret of `opensmtpd_secrets` as `/config/secrets` |
| `exec_start_pre` | the copies of the certificate of `opensmtpd_tls`, written as `ExecStartPre=` to `[Service]` of the quadlet unit |
| `requires`, `wants`, `after`, `part_of`, `binds_to`, `requires_mounts_for` | not set, written to `[Unit]` of the quadlet unit |

### Validation

The role checks before any change:

- `opensmtpd_config` is a dictionary of allowed statements without `include`,
  the named statements are dictionaries with names of letters, digits, `_`, `.` and `-`,
  the values are strings, numbers, `true`, `null` or lists of them without line breaks
- the pki of the realm and the table `secrets` are not set in `opensmtpd_config`
- `opensmtpd_tls` only contains `realm` and `dir`, `dir` is an absolute path, `fullchain.pem` and `privkey.pem` of the realm exist on the host
- `opensmtpd_secrets` is a list of entries with name, data and target, the names are unique, the target is `secrets` and set once, the data is a string
- `opensmtpd_environment` is a dictionary without line breaks, the environment of the container only contains allowed variables

Before a changed `smtpd.conf` replaces the former one, the role checks it with `smtpd -n` in a container of the image
with the home directory, the files of the realm in `/config/tls` and the secret, `smtpd -n` also loads the certificate and the key.
A rejected configuration stops the role with the messages of `smtpd`, `smtpd.conf` stays unchanged.

### Check mode

In check mode a new home directory is not created, the role stops after the validation, there are no files to compare.
A realm of `opensmtpd_tls` that does not exist yet is only reported, `pki_easyrsa_deploy` and `pki_certbot` create it only in a real run.
`smtpd -n` does not run in check mode.

### Restart and updates

OpenSMTPD is started and enabled. It is restarted only if it was running and `smtpd.conf`, the secret or the quadlet unit changed,
smtpd reads them only at the start. Updates of the image are done by `container_update` with `opensmtpd_autoupdate_enabled` and `opensmtpd_autoupdate_schedule`,
a renewed certificate restarts OpenSMTPD by `pki_update` with `opensmtpd_pki_update_enabled` and `opensmtpd_pki_update_schedule`.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs with Debian 13 on a macOS controller.
`prepare` installs podman with `container_podman`, pulls the image, creates a CA and the certificate of the realm `mx.molecule.test`
with `openssl` on the controller and the realm with the structure of `pki_easyrsa_deploy` and of `pki_certbot` on `molecule-opensmtpd`.
`check` runs `converge` with `--check` on the VMs where the role never ran.

| Platform | Test case |
|---|---|
| `molecule-opensmtpd-default` | The mandatory values only, port 25 relays only the mails of the container |
| `molecule-opensmtpd` | TLS of the realm, submission on port 587 with AUTH from the table of the secret, relay of authenticated users to an unreachable host |

`side_effect` runs the role with `opensmtpd_config` not a dictionary, `include` and an unknown statement, an invalid name, a value of the wrong type
and a line break, the table `secrets` in `opensmtpd_config`, an unknown target, data that is no string, a secret without data, a realm missing on the host, `opensmtpd_tls.dir` without the realm, a relative `dir` and an unknown key,
an unknown environment variable and an option that `smtpd -n` rejects, and checks that it fails with the expected message
and the quadlet unit and `smtpd.conf` are unchanged (tasks marked `expect ERROR`).
On `molecule-opensmtpd` it changes `smtp` and switches to the certificate of certbot with `opensmtpd_tls.dir`, OpenSMTPD has to restart.
`verify` checks the quadlet unit, `smtpd.conf`, the files and modes of the home directory, the timer of `pki_update` with the certificate of certbot,
the service and the secret in the container,
and talks to OpenSMTPD with the module `mail_opensmtpd_test_smtp`: the banner and the refused relay on port 25 (with STARTTLS on `molecule-opensmtpd`),
AUTH with a wrong and the right password on port 587 and a mail that stays in the queue.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd mail_opensmtpd
MOLECULE_TART_IMAGE='debian' molecule test
```
