mqttwarn runs in the container image `c0d3.sh/container/mqttwarn-docker` (`latest` by default, `mqttwarn_version` sets the tag) as podman quadlet.
The image installs mqttwarn with all optional dependencies of the services and runs it as the user `mqttwarn` (999).
`<mqttwarn_home>/etc` is mounted to `/etc/mqttwarn`, it contains `mqttwarn.ini` and the files of `mqttwarn_files`.
mqttwarn subscribes to the topics of the broker and passes the messages to services, e.g. mail, Pushover or a file.

### Configuration

`mqttwarn_config` contains the sections of `mqttwarn.ini` with their options, it is merged recursively over the default of the role,
`null` removes a section or an option. The sections are described in the [configuration of mqttwarn](https://mqttwarn.readthedocs.io/en/latest/configure/mqttwarn.ini.html):

- `defaults`: the broker, the logging, the functions and the services started with `launch`
- `config:<service>`: the options and the `targets` of a service, a dictionary of the targets with their addresses
- `failover`: the `targets` of the messages of mqttwarn itself
- `cron`: functions with their period in seconds
- every other section is a topic with its `targets` (e.g. `smtp:admin`) and options like `format`, `title` or `priority`

mqttwarn evaluates the values of `defaults` and `config:<service>` as Python literals, the role writes them like that:
strings are quoted, booleans are `True` and `False`, lists and dictionaries are written as Python literals.
mqttwarn reads the options of the topics, `failover` and `cron` as text, the role writes strings without quotes
and removes options set to `false`, mqttwarn reads every text as true. Lists of `launch` and of the `targets` of topics and `failover` are joined by commas.
`defaults.hostname` is mandatory.

```yaml
mqttwarn_config:
  defaults:
    hostname: 'mqtt.example.org'
    username: 'mqttwarn'
    functions: 'icinga2.py'
    launch: [ 'log', 'smtp' ]
  'config:smtp':
    server: 'mail.example.org:587'
    sender: 'mqttwarn@example.org'
    username: 'mqttwarn'
    starttls: true
    targets:
      admin: [ 'admin@example.org' ]
  'icinga2/+/+':
    targets: [ 'smtp:admin' ]
    priority: 'icinga2_priority()'
```

The default of the role:

```yaml
defaults:
  clientid: 'mqttwarn'
  lwt: 'clients/mqttwarn'
  lwt_alive: '1'
  lwt_dead: '0'
  skipretained: true
  cleansession: false
  protocol: 3
  logfile: 'stream://sys.stderr'
  loglevel: 'INFO'
  filteredmessagesloglevel: 'INFO'
  logformat: '%(asctime)-15s %(levelname)-8s [%(name)-25s] %(message)s'
  launch: [ 'log' ]
  status_publish: true
  status_topic: 'mqttwarn/$SYS'
'config:log':
  targets: { debug: [ 'debug' ], info: [ 'info' ], warn: [ 'warn' ], crit: [ 'crit' ], error: [ 'error' ] }
failover:
  targets: [ 'log:error' ]
```

The time zone of the container is `mqttwarn_timezone`, set by podman, the image sets no `TZ`.

### Secrets

mqttwarn expands `${FILE:<path>}` in the options of `mqttwarn.ini` with the content of the file, so the secrets are files referenced in the configuration.
`mqttwarn_secrets` is a list of podman secrets with `name`, `data` and `target`, the target is `<section>.<option>`:
`defaults.password` (the password of the broker) or `config:<service>.<option>` with the options of `monitoring_mqttwarn__config_secret_options`
(`apikey`, `dns_keyblob`, `pass`, `password` and `token`). The role mounts the secret to `/run/secrets/<name>` (owner 999, mode `0400`)
and writes `<option> = "${FILE:/run/secrets/<name>}"`, neither `mqttwarn.ini` nor the quadlet unit contain the secret.

```yaml
mqttwarn_secrets:
  - name: 'mqttwarn_mqtt_password'
    data: "{{ vault_mqttwarn_mqtt_password }}"
    target: 'defaults.password'
  - name: 'mqttwarn_smtp_password'
    data: "{{ vault_mqttwarn_smtp_password }}"
    target: 'config:smtp.password'
```

mqttwarn evaluates the quoted content of the file as Python string, so secrets must not contain line breaks, double quotes or backslashes.
The options of the secrets must not be set in `mqttwarn_config`, the section of a secret of a service has to be part of `mqttwarn_config`.

### Files

`mqttwarn_files` is a list of files of the controller copied to `<mqttwarn_home>/etc` (owner 999, mode `0640`), e.g. the functions of `defaults.functions`.
mqttwarn reads relative paths of `mqttwarn.ini` relative to `/etc/mqttwarn`. The role contains `icinga2.py` with the function `icinga2_priority`
for the messages of Icinga, a relative path of `mqttwarn_files` is searched in the files of the role and of the playbook.

```yaml
mqttwarn_files: [ 'icinga2.py' ]
```

### Allowed options

The role only allows the options of `monitoring_mqttwarn__config_defaults_allowed` in `defaults`, `targets` in `failover`,
the options of `monitoring_mqttwarn__config_topic_allowed` in the topics, the services of `monitoring_mqttwarn__config_services`
(or a section with `module`) and `TZ` in `mqttwarn_environment`, it stops before any change if unknown options, services or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password that has to be passed as secret.
The lists are generated from `mqttwarn/configuration.py`, `mqttwarn/core.py`, `mqttwarn/context.py` and `mqttwarn/services` of mqttwarn 0.36.1,
the image may contain another version. The options of the services differ, their names are checked with `^[a-z0-9_]+$`.
`mqttwarn_environment` has no default, the check of the environment uses the environment of the container after merging `mqttwarn_container`.

### Container

Ports, volumes, labels, additional hosts (`etc_hosts`) and dependencies are changed with `mqttwarn_container`, it is merged over the default of the container.
The merge is not recursive, `mqttwarn_container.volumes` replaces the configuration, e.g. to mount the certificates of `defaults.ca_certs`
the volume of the configuration has to be part of the list.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

```yaml
mqttwarn_container:
  wants: [ 'mosquitto.service' ]
  after: [ 'mosquitto.service' ]
```

### Validation

The role checks before any change:

- `mqttwarn_secrets` is a list of entries with `name`, `data` and `target` and unique names, every target is a known secret of an existing section and set once,
  the data are strings without line breaks, double quotes and backslashes, podman checks the names of the secrets
- `mqttwarn_config` contains dictionaries of known options, known services, topics with `targets`, no secrets, booleans that are booleans,
  periods of `cron` that are numbers, lists and dictionaries of strings and numbers, no line breaks and `defaults.hostname`
- `mqttwarn_files` is a list of files with unique names matching `^[A-Za-z0-9_][A-Za-z0-9_.-]*$`, `mqttwarn.ini` is not allowed
- `mqttwarn_environment`, if set, is a dictionary without line breaks
- only `TZ` without line breaks is set in the environment of the container

If `mqttwarn_container` or `mqttwarn_config` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter. mqttwarn checks the values of the options when it uses them.

### Check mode

The role runs with `--check`, also on a host where it never ran, and reports the directories, the files, `mqttwarn.ini`, the secrets and the quadlet unit.
The start and the wait for mqttwarn do not run in check mode.

### Restart and updates

mqttwarn is restarted if it was running and `mqttwarn.ini`, a file, a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the error and the journal of the service.
mqttwarn has no API and logs the login to the broker only with `DEBUG`, it exits if the broker does not answer.
The role waits until mqttwarn runs for 10 seconds and fails with the log if it restarted by itself or logged a refused login.
Updates of the image are done by `container_update` with `mqttwarn_autoupdate_enabled: true` and `mqttwarn_autoupdate_schedule`,
without `mqttwarn_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former version of the role configured mqttwarn with single variables, they are options of `mqttwarn_config` now.
The role ignores the former variables.

| Former variable | Replacement |
|---|---|
| `mqttwarn_mqtt_hostname`, `mqttwarn_mqtt_port`, `mqttwarn_mqtt_username` | `defaults.hostname`, `defaults.port`, `defaults.username` |
| `mqttwarn_mqtt_password` | secret with target `defaults.password` |
| `mqttwarn_mqtt_clientid`, `mqttwarn_mqtt_lwt`, `mqttwarn_mqtt_lwt_alive`, `mqttwarn_mqtt_lwt_dead` | `defaults.clientid`, `defaults.lwt`, `defaults.lwt_alive`, `defaults.lwt_dead` |
| `mqttwarn_mqtt_skipretained`, `mqttwarn_mqtt_cleansession`, `mqttwarn_mqtt_protocol` | `defaults.skipretained`, `defaults.cleansession`, `defaults.protocol` |
| `mqttwarn_mqtt_tls`, `mqttwarn_mqtt_tls_version`, `mqttwarn_mqtt_tls_insecure` | `defaults.tls`, `defaults.tls_version`, `defaults.tls_insecure` |
| `mqttwarn_ca_certs`, `mqttwarn_certfile`, `mqttwarn_keyfile` | `defaults.ca_certs`, `defaults.certfile`, `defaults.keyfile` |
| `mqttwarn_logfile`, `mqttwarn_loglevel`, `mqttwarn_filteredmessagesloglevel`, `mqttwarn_logformat` | `defaults.logfile`, `defaults.loglevel`, `defaults.filteredmessagesloglevel`, `defaults.logformat` |
| `mqttwarn_functions` | `defaults.functions` |
| `mqttwarn_launch` | `defaults.launch` |
| `mqttwarn_status_publish`, `mqttwarn_status_topic` | `defaults.status_publish`, `defaults.status_topic` |
| `mqttwarn_mqtt_realm` | removed, it was not used |
| `mqttwarn_config` (list of services with `name`, `host`, `port`, `username`, `password`, `cacert` and `targets`) | sections `config:<name>`, the targets are a dictionary of lists, passwords are secrets |
| `mqttwarn_failover` | `failover.targets` |
| `mqttwarn_topics` (list with `topic`, `targets`, `priority`, `timeout`, `format`, `notify_only_on_timeout`) | sections named like the topic |
| `podman___update_mode` | `mqttwarn_autoupdate_enabled` |

Changed behavior:

- the password of the broker and the passwords of the services were part of `mqttwarn.ini`, they are secrets read from files now
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set by podman with `mqttwarn_timezone`
- the default of `failover` was `log:error, file:mqttwarn` without a target `mqttwarn` of the service `file`, it is `log:error` now
- the role checks the options, the services and the topics, mqttwarn ignored unknown options
- mqttwarn is restarted if the configuration, a file or a secret changed, the role waits until mqttwarn runs and shows the log if it fails,
  the handler is removed
- `mqttwarn_labels`, `mqttwarn_environment`, `mqttwarn_secrets`, `mqttwarn_autoupdate_enabled` and `mqttwarn_autoupdate_schedule` are new,
  the dependencies of the quadlet unit are set with `mqttwarn_container`
- the tags are `monitoring` and `monitoring_mqttwarn`

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `c0d3.sh` and Docker Hub.

| Platform | Test case |
|---|---|
| `molecule-mqttwarn-default` | Only `defaults.hostname`, the broker without password |
| `molecule-mqttwarn` | IPv6, labels, dependencies, the password of the broker as secret, a file with functions, the service `file` and a topic with a function |

`prepare` creates the podman network, pulls the images and starts Mosquitto, on `molecule-mqttwarn` with a password file.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `mqttwarn_container` and `mqttwarn_config` not a dictionary, an unknown option of `defaults`, a boolean that is no boolean,
an unknown service, a topic without targets, an unknown option of a topic, a password in `mqttwarn_config`, a dictionary in a list, a line break in a value,
a secret without target, an unknown secret, the secret of a missing section, a double quote in a secret, an invalid name of a file,
`mqttwarn_environment` not a dictionary, an unknown variable and a line break in the environment of the container
and checks that it fails with the expected message and the quadlet unit and `mqttwarn.ini` are unchanged (tasks marked `expect ERROR`),
then it changes `defaults.loglevel` on `molecule-mqttwarn`, `mqttwarn.ini` changes and mqttwarn has to restart,
`molecule-mqttwarn-default` runs again without a change and mqttwarn must not restart.
`verify` checks the quadlet unit with the mounted secret and without the password and the volumes of the time zone, the lines of `mqttwarn.ini`
with the reference of the secret, the owner and the mode of the files, the service without automatic restarts, the time zone and no `TZ` in the environment,
the status `mqttwarn/$SYS/version` published to the broker and, on `molecule-mqttwarn`, that a published message is written to the file
of the service `file`, formatted by the function of `molecule_funcs.py`.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd monitoring_mqttwarn
MOLECULE_TART_IMAGE='debian' molecule test
```
