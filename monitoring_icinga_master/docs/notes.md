Icinga 2 runs as master in the official container image [icinga/icinga2](https://hub.docker.com/r/icinga/icinga2) as podman quadlet.
The image links `/etc/icinga2`, `/var/lib/icinga2`, `/var/cache/icinga2`, `/var/log/icinga2` and `/var/spool/icinga2` to `/data`,
`/data` is a volume of the image with its files, e.g. the scripts of the mail notifications and `features-available`.
The role mounts only its configuration and the state of Icinga, everything else of `/data` comes from the image:

| Host | Container |
|---|---|
| `<icinga_master_home>/lib` | `/data/var/lib/icinga2` (certificates, API, state) |
| `<icinga_master_home>/log` | `/data/var/log/icinga2` |
| `<icinga_master_home>/spool` | `/data/var/spool/icinga2` |
| `<icinga_master_home>/cache` | `/data/var/cache/icinga2` |
| `<icinga_master_home>/run` | `/data/var/run` |
| `<icinga_master_home>/etc/<file>` | `/data/etc/icinga2/<file>`, read-only, for `icinga2.conf`, `constants.conf`, `zones.conf`, `endpoints.conf`, `conf.d`, `features-enabled` and `zones.d` |
| `<icinga_master_home>/tmp` | `/tmp` |
| `<icinga_master_home>/plugins` | `/usr/local/lib/nagios/plugins`, read-only |

### Configuration

`icinga_master_config` contains the features of Icinga, one key per feature with the attributes of its object.
It is merged recursively over the default of the role. A feature with a dictionary is enabled and written to `features-enabled/<feature>.conf`,
`null` or `false` disables a feature of the default.

```yaml
icinga_master_config:
  api:
    accept_commands: true
  mainlog:
    severity: 'warning'
  debuglog:
    severity: 'debug'
    path: '/var/log/icinga2/debug.log'
  influxdb2:
    host: 'influxdb.example.org'
    port: 8086
    organization: 'monitoring'
    bucket: 'icinga2'
    flush_threshold: 1024
    flush_interval: 10
    host_template:
      measurement: '$host.check_command$'
      tags:
        hostname: '$host.name$'
    service_template:
      measurement: '$service.check_command$'
      tags:
        hostname: '$host.name$'
        service: '$service.name$'
  notification: null
```

The default of the role enables the features of the former versions:

```yaml
api:
  accept_config: false
  accept_commands: false
  bind_host: '0.0.0.0'
  bind_port: 5665
checker: {}
mainlog:
  severity: 'information'
  path: '/var/log/icinga2/icinga2.log'
notification: {}
```

The values are written as values of the Icinga DSL: strings are quoted, numbers and booleans are literals, lists are arrays and dictionaries
are dictionaries with quoted keys. Durations are numbers of seconds, e.g. `flush_interval: 10`.
`null` removes an attribute, `false` removes it as well unless the attribute is a boolean, then `false` is written.

The objects of the monitoring are lists as before, they are written to `conf.d` as Icinga DSL:
`icinga_master_hosts`, `icinga_master_services`, `icinga_master_templates`, `icinga_master_commands` (the default contains the mail notification commands),
`icinga_master_notifications`, `icinga_master_timeperiods`, `icinga_master_users`, `icinga_master_user_groups`, `icinga_master_host_groups`,
`icinga_master_service_groups`, `icinga_master_host_dependencies`, `icinga_master_service_dependencies` and `icinga_master_api_users`.
The satellites and agents are `icinga_master_zones` (endpoint and zone below the zone of the master),
their hosts and services are `icinga_master_zone_hosts` and `icinga_master_zone_services`, dictionaries of lists by zone written to `zones.d/<zone>`.

```yaml
icinga_master_api_users:
  - name: 'icingaweb2'
    permissions: [ '*' ]
icinga_master_hosts:
  - name: 'server.example.org'
    import: [ 'generic-host' ]
    address: '192.0.2.10'
    check_command: 'hostalive'
icinga_master_services:
  - name: 'ssh'
    import: [ 'generic-service' ]
    check_command: 'ssh'
    assign: [ 'host.address' ]
```

### Secrets

The DSL of Icinga cannot read files: there is no function to read a file and `include` is a statement, not a value.
The image reads no `*_FILE` variables either, the only other way would be `getenv()` with the passwords in the environment of the container.
So the secrets are constants of Icinga in one file, the podman secret `<container name>-config` (`icinga-master-config`).

`icinga_master_secrets` is a list of entries with `name`, `data` and `target`:

- the target is `<feature>.<attribute>` of the attributes Icinga hides from its API, these are `api.ticket_salt`, `icingadb.password`, `influxdb.password`,
  `influxdb2.auth_token` and `elasticsearch.password`, the feature has to be enabled in `icinga_master_config`
- or `api_users.<name>.password` for the password of an entry of `icinga_master_api_users`
- the name is the name of the constant `Secret_<name>`, it starts with a letter or `_`, followed by letters, digits and `_`

```yaml
icinga_master_secrets:
  - name: 'icinga_ticket_salt'
    data: "{{ vault_icinga_ticket_salt }}"
    target: 'api.ticket_salt'
  - name: 'icinga_api_icingaweb2'
    data: "{{ vault_icinga_api_icingaweb2 }}"
    target: 'api_users.icingaweb2.password'
  - name: 'icinga_influxdb2'
    data: "{{ vault_icinga_influxdb2_token }}"
    target: 'influxdb2.auth_token'
```

The role writes `const Secret_<name> = "<data>"` for every secret to the podman secret and mounts it with
`type=mount,target=/run/secrets/icinga-master-config,uid=5665,gid=5665,mode=0400`, `icinga2.conf` includes it after `constants.conf`.
The configuration on the host references the constants, e.g. `password = Secret_icinga_api_icingaweb2`, the passwords are neither part of the files on the host,
nor of the quadlet unit or the environment. Without secrets the role removes the podman secret and `icinga2.conf` does not include it.

The passwords of other objects, e.g. `vars` of `icinga_master_users`, are written as they are.

### Allowed variables

The role only allows the features of `monitoring_icinga_master__features` with the attributes of `monitoring_icinga_master__config_allowed`,
the secrets of `monitoring_icinga_master__secrets_allowed` and the environment variables in `monitoring_icinga_master__environment_allowed`,
it stops before any change if unknown features, attributes, secrets or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password that has to be passed as secret.
The attributes are generated from `lib/*/*.ti` of Icinga 2 v2.16.0, without deprecated attributes.
The attribute `basic_auth` of `influxdb` contains a password, it is not allowed, use `username` and the secret `influxdb.password`.

`icinga_master_environment` has no default and only takes `ICINGA_LOG_LEVEL` of the image, without it the quadlet unit has no environment.
The variables of the node setup of the image (`ICINGA_MASTER`, `ICINGA_CN`, …) and `MSMTPRC` are not allowed:
the role configures the node itself and `MSMTPRC` may contain a password.
The check of the environment uses the environment of the container after merging `icinga_master_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies are changed with `icinga_master_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`icinga_master_container.environment` replaces the environment including `icinga_master_environment`.
The dependencies of the quadlet unit are lists of units in `icinga_master_container`: `requires`, `wants`, `after`, `part_of` and `binds_to`
are written as `Requires=`, `Wants=`, `After=`, `PartOf=` and `BindsTo=` to `[Unit]`.

```yaml
icinga_master_container:
  publish: [ '5665:5665' ]
  wants: [ 'redis-icingadb.service' ]
  after: [ 'redis-icingadb.service' ]
```

The plugins of `<icinga_master_home>/plugins` are mounted read-only to `/usr/local/lib/nagios/plugins` (`PluginLocalDir`), the role copies `pushover.sh` there.
The CheckCommands of the plugins of the agents are written to `conf.d/commands`, among them `commands-dsa.conf` (`dsa-*`) and `commands-madrisan.conf` (`madrisan-*`)
of the plugins `dsa` and `madrisan` of `monitoring_plugins`, so the master can schedule these checks on the agents.

### Certificates

The certificates come from `icinga_cert_source_dir`: `<node name>/chain.pem` (or `icinga_cert_ca_file`), `<node name>/fullchain.pem` and `<node name>/privkey.pem`.
`ExecStartPre` of the quadlet unit installs them with `install` on every start to `<icinga_master_home>/lib/certs` (`/var/lib/icinga2/certs`) as `ca.crt`, `<node name>.crt` and `<node name>.key`
for the user of Icinga (5665), `install` follows the links of certbot and sets owner and mode, the key has mode `0400`.
A renewed certificate is used after the next restart: the timer of `pki_update` restarts Icinga if `fullchain.pem` is newer than the start of Icinga,
every four hours by default (`icinga_master_pki_update_schedule`), `icinga_master_pki_update_enabled: false` disables it.
The image runs its node setup only without `ca.crt`, so it never runs, the role configures the node itself.

### Validation

The role checks before any change:

- `icinga_master_secrets` is a list of entries with `name`, `data` and `target` and unique names,
  every target is a known secret of an enabled feature or of an API user and set once, names are names of constants, the data are strings without line breaks
- `icinga_master_config` contains known features with dictionaries, `null` or `false`, known attributes, booleans for boolean attributes,
  no secrets and no line breaks
- the former single variables of the role are not set, the message names their replacement
- the lists of objects are lists of dictionaries, the entries of `api_users`, `commands`, `host_groups`, `hosts`, `service_groups`, `timeperiods`,
  `user_groups`, `users` and `zones` have unique names, the API users have no `password`,
  `icinga_master_zone_hosts` and `icinga_master_zone_services` are dictionaries of lists
- `icinga_master_environment`, if set, is a dictionary without line breaks, only allowed environment variables are set in the container

If `icinga_master_container` or `icinga_master_config` is no dictionary, merging it with the default fails before anything changes.
Icinga checks the objects and the values of the attributes at the start.

### Restart and updates

Icinga is restarted if it was running and a file of the configuration, a feature, the podman secret or the quadlet unit changed, otherwise it is started and enabled.
Before the restart the role checks the configuration with `icinga2 daemon -C` in the running container. If Icinga rejects it, the role does not restart Icinga
and fails with the output of the check, Icinga keeps running with the former configuration. The files on the host are written already,
a second run without a change does not restart Icinga either, fix the configuration and run the role again.
`icinga2.conf`, `constants.conf`, `zones.conf` and `endpoints.conf` are single files mounted into the container, the running container may still see
their former version, `conf.d`, `features-enabled` and `zones.d` are directories and show the new files.
If the start fails, the role shows the journal of the service. With the feature `api` the role waits until the API answers and shows the journal otherwise,
Icinga exits if the configuration is invalid.
Updates of the image are done by `container_update` with `icinga_master_autoupdate_enabled: true` and `icinga_master_autoupdate_schedule`,
without `icinga_master_autoupdate_schedule` the schedule of `container_update` is used.
A renewed certificate restarts Icinga by `pki_update` with `icinga_master_pki_update_enabled` and `icinga_master_pki_update_schedule`.

### Migration

The features are set with `icinga_master_config` now, the passwords with `icinga_master_secrets`. The role rejects the former variables and names their replacement.

| Former variable | Replacement |
|---|---|
| `icinga_master_api_accept_config`, `icinga_master_api_accept_commands`, `icinga_master_api_bind_host`, `icinga_master_api_bind_port` | `accept_config`, `accept_commands`, `bind_host`, `bind_port` in `api` |
| `icinga_master_main_log_file`, `icinga_master_main_log_severity` | `path`, `severity` in `mainlog` |
| `icinga_master_debug_log_file`, `icinga_master_debug_log_severity` | `path`, `severity` in `debuglog` |
| `icinga_master_icingadb_host`, `icinga_master_icingadb_port` | `host`, `port` in `icingadb` |
| `icinga_master_icingadb_password` | secret with target `icingadb.password` |
| `icinga_master_influxdb_host`, `_port`, `_organization`, `_bucket` | `host`, `port`, `organization`, `bucket` in `influxdb2` |
| `icinga_master_influxdb_send_metadata`, `icinga_master_influxdb_send_thresholds` | `enable_send_metadata`, `enable_send_thresholds` in `influxdb2` |
| `icinga_master_influxdb_auth_token` | secret with target `influxdb2.auth_token` |
| `icinga_master_features_enabled` | the features with a dictionary in `icinga_master_config` |
| `icinga_master_features_disabled` | `null` for a feature of the default |
| `icinga_master_ticket_salt` | secret with target `api.ticket_salt` |
| `password` of `icinga_master_api_users` | secret with target `api_users.<name>.password` |
| `icinga_master_use_podman` | removed, it was not used |
| `podman___update_mode` | `icinga_master_autoupdate_enabled` |
| `env` of `icinga_master_container` | `environment` of `icinga_master_container` or `icinga_master_environment` |

Changed behavior:

- the former template of `influxdb2` set `host_template`, `service_template`, `flush_threshold: 1024` and `flush_interval: 10s`, they are attributes in `icinga_master_config` now
  (see the example above)
- the features are files in `features-enabled`, the role removes `features-available` and every other file in `features-enabled`
- `TicketSalt` of `constants.conf` is removed, `ticket_salt` of `api` is only set with the secret `api.ticket_salt`
- `ICINGA_MASTER=1` is removed from the environment, the node setup of the image never ran because `ExecStartPre` copies `ca.crt` before the start
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set with `icinga_master_timezone`
- the files are written for the user 5665 with `0400`, the directories with `0750`
- `<icinga_master_home>/data` is not mounted to `/data` anymore, it hid the files of the image, e.g. the scripts of the mail notifications
  `mail-host-notification` and `mail-service-notification` of `icinga_master_commands`. The directories on the host are
  `lib`, `log`, `spool`, `cache`, `run` and `etc` now, the role does not move the files of former versions.
  Move the state before the first run and remove `<icinga_master_home>/data` afterwards:
  `mv <icinga_master_home>/data/var/lib/icinga2 <icinga_master_home>/lib`, `mv <icinga_master_home>/data/var/log/icinga2 <icinga_master_home>/log`,
  `mv <icinga_master_home>/data/var/spool/icinga2 <icinga_master_home>/spool`,
  `mv <icinga_master_home>/data/var/cache/icinga2 <icinga_master_home>/cache`
- the mail notifications use `mail` of the image (msmtp), they need `/var/lib/icinga2/.msmtprc` (`<icinga_master_home>/lib/.msmtprc`),
  the role does not manage it yet
- Icinga is restarted if the configuration changed, the handler is removed, the tags are `monitoring` and `monitoring_icinga_master`
- `ExecStartPre` uses `install` instead of `cp -uL`, `chown` and `chmod`, it does not depend on the timestamps anymore,
  the timer of `pki_update` restarts Icinga after a renewal of the certificate

Fixed bugs:

- `conf.d/users.conf` wrote `vars` and `options` of a user only with `email` and read `options` of an undefined `service`
- `permissions` of an API user was mandatory

### Tests

The molecule scenario `default` uses tart with the VMs `molecule-icinga-master-default` with the mandatory variables and `molecule-icinga-master` with the options.
`prepare` creates a CA and the certificate of the node with `openssl` in `icinga_cert_source_dir`, pulls the image and starts Redis with a password on `molecule-icinga-master`.
`side_effect` runs the role with `icinga_master_container` and `icinga_master_config` not a dictionary, an unknown feature, a feature that is no dictionary,
an unknown attribute, a boolean that is no boolean, a password in `icinga_master_config` and in `icinga_master_api_users`, a secret without target,
an unknown secret, the secret of a missing API user and of a disabled feature, a secret name that is no constant, a former variable,
`icinga_master_hosts` not a list and an unknown environment variable and checks that it fails with the expected message
and the quadlet unit, `mainlog.conf` and `api-users.conf` are unchanged (tasks marked `expect ERROR`),
then it writes a host with an unknown check command on `molecule-icinga-master`, `icinga2 daemon -C` has to reject it and Icinga must not restart,
then it changes `mainlog.severity` on `molecule-icinga-master`, `mainlog.conf` changes, Icinga has to restart and the container has to mount the new file.
`verify` checks the quadlet unit with the `install` lines of `ExecStartPre`, owner and mode of the key, the timer of `pki_update`, the enabled features and their files, the lines of the configuration with the constants of the secrets,
that no password is part of the files, the quadlet unit or the environment, the mounted podman secret, the service,
`icinga2 daemon -C` in the container, the scripts of the mail notifications and `features-available` of the image in the container, the API without login (401), the hosts of the API with the API user and the secret password
and the objects that Icinga writes to Redis with the password of `icingadb`.

```shell
cd monitoring_icinga_master
MOLECULE_TART_IMAGE='debian' molecule test
```
