The role runs the [Mosquitto](https://mosquitto.org/) MQTT broker with the image `docker.io/eclipse-mosquitto` as podman quadlet.
It writes `mosquitto.conf`, the users and the ACL to `<mosquitto_home>/config`, mounted read only to `/mosquitto/config`,
the broker keeps its persistence in `<mosquitto_home>/data`.

```yaml
- name: 'Configure mqtt.example.org'
  become: true
  hosts: 'mqtt'
  roles:
    - 'common_filters'
    - 'common_globals'
    - 'smarthome_mosquitto'
```

### Configuration

`mosquitto_config` holds the options of `mosquitto.conf`, it is merged into the default of the role:

```yaml
persistence: true
persistence_location: '/mosquitto/data/'
log_dest: 'stdout'
allow_anonymous: false
listener:
  - port: 1883
```

- A string or number writes `option value`, a list writes one line per element (e.g. `log_type`, `topic`), `null` removes the option.
- `true` and `false` are written as `true` and `false`. Unlike `time_chrony`, `false` does not remove an option,
  Mosquitto has options that are `true` by default (e.g. `retain_available`), they are switched off with `false`.
- The broker logs to the journal of the service (`log_dest stdout`), `journalctl -u mosquitto` shows the log.
- The file is written in this order: the general options, the plugins of the users and the ACL, the listeners, the bridges and,
  if a bridge has a secret value, `include_dir` for the bridges with secrets (see Secrets).

### Listeners and bridges

Listeners and bridges are sections of `mosquitto.conf`, the options after `listener` or `connection` belong to that section.
`listener` and `connection` of `mosquitto_config` are lists, one entry per section. They replace the default completely,
so `mosquitto_config.listener` has to contain the listener on 1883 as well if it is still needed.

```yaml
mosquitto_config:
  log_type: [ 'error', 'warning', 'notice' ]
  listener:
    - port: 1883
    - port: 8883
      cafile: '/mosquitto/pki/ca.crt'
      certfile: '/mosquitto/pki/server.crt'
    - port: 9001
      bind_address: '0.0.0.0'
      protocol: 'websockets'
  connection:
    - name: 'cloud'
      address: 'mqtt.example.org:8883'
      remote_username: 'home'
      bridge_cafile: '/etc/ssl/certs/ca-certificates.crt'
      topic: [ 'sensors/# out 1', 'commands/# in 1' ]
mosquitto_secrets:
  - name: 'mosquitto-tls-key'
    data: "{{ vault_mosquitto_tls_key }}"
    target: 'listener.8883.keyfile'
  - name: 'mosquitto-cloud-password'
    data: "{{ vault_mosquitto_cloud_password }}"
    target: 'connection.cloud.remote_password'
```

- A listener needs `port`, `bind_address` is optional, both are written as `listener <port> <bind_address>`.
  `realm` of a listener or a bridge sets the certificate and the key of a realm (see Certificates of realms).
  The ports of the listeners have to be unique, the secrets name the listener by its port.
- A bridge needs `name`, written as `connection <name>`. The names consist of letters, digits, `_`, `.` and `-` and have to be unique.
- Files of listeners and bridges (e.g. certificates) are mounted with `mosquitto_container.volumes`,
  the list replaces the volumes of the default, which have to be part of it.
- The ports published on the host are `1883` and `8883`, other listeners need `mosquitto_container.publish`.

### Certificates of realms

`mosquitto_realms` is a list of realms of the PKI with local certificates, e.g. of `pki_easyrsa_deploy`.
Every realm has `<realm>/fullchain.pem` and `<realm>/privkey.pem` in the directory of the realms (`common_globals__pki_realms_dir`, default `/etc/pki/realms`).
The quadlet unit installs them on every start of Mosquitto with `ExecStartPre` to `<mosquitto_home>/certs/<realm>.crt` (`0644`) and `<realm>.key` (`0400`),
owned by the user `1883` of the image, `install` follows the links of the realm. The directory is mounted read only to `/mosquitto/certs`.

A listener or a bridge uses a realm with `realm`, the role writes `certfile` and `keyfile` of the listener or `bridge_certfile` and `bridge_keyfile` of the bridge:

```yaml
mosquitto_realms: [ 'mqtt.example.org', 'mqtt.example.net' ]
mosquitto_config:
  listener:
    - port: 1883
    - port: 8883
      realm: 'mqtt.example.org'
    - port: 8884
      realm: 'mqtt.example.net'
  connection:
    - name: 'cloud'
      address: 'mqtt.example.com:8883'
      bridge_cafile: '/etc/ssl/certs/ca-certificates.crt'
      # The certificate of the realm is the client certificate of the bridge
      realm: 'mqtt.example.org'
      topic: [ 'sensors/# out 1' ]
```

- A listener or bridge with `realm` must not set the certificate or the key itself, neither in `mosquitto_config` nor as secret.
  `cafile` (e.g. for client certificates) stays an option of the listener, its file is mounted with `mosquitto_container.volumes`.
- The certificates of removed realms are removed from `<mosquitto_home>/certs`.
- With `mosquitto_pki_update_enabled` (default `true`) the role installs the timer of `pki_update` for the service,
  its timer (`mosquitto_pki_update_schedule`, default `*-*-* 00/4:00:00`) restarts Mosquitto if one of the `fullchain.pem` of the realms is newer than the start of Mosquitto.
  Mosquitto reloads certificates on SIGHUP as well, but the timer compares the certificates with the start of the service, after a SIGHUP it would fire again and again.
  The timer stays if the realms are removed later.
- A key that does not come from a realm is passed as secret with the target `listener.<port>.keyfile` (see Secrets).

### Users and ACL

`mosquitto_users` holds the users by their names with `password` and `acl`, `mosquitto_acl` the lines of anonymous clients and the patterns of all users:

```yaml
mosquitto_users:
  sensor:
    password: "{{ vault_mosquitto_sensor_password }}"
    acl: [ 'write sensors/#' ]
  homeassistant:
    password: "{{ vault_mosquitto_homeassistant_password }}"
    acl: [ 'readwrite #' ]
mosquitto_acl:
  anonymous: [ 'read $SYS/broker/uptime' ]
  pattern: [ 'readwrite users/%u/#' ]
```

- The users are written to `<mosquitto_home>/config/passwd` by the module `smarthome_mosquitto_passwd`, with hashes like `mosquitto_passwd` of Mosquitto 2.1
  (`sha512-pbkdf2`, 20000 iterations, salt of 64 bytes). A hash is kept as long as it matches the password, so the file only changes with a user or a password.
  Users that are not listed are removed, the file is owned by `1883` with mode `0600`.
- An ACL line is the access (`read`, `write`, `readwrite` or `deny`) and the topic. `anonymous` is written as `topic` lines before the first user,
  `pattern` as `pattern` lines, the lines of a user follow `user <name>`. The file is `<mosquitto_home>/config/acl`.
- The users and the ACL are read by the plugins `mosquitto_password_file.so` and `mosquitto_acl_file.so` of the image.
  `password_file` and `acl_file` of `mosquitto.conf` are deprecated since Mosquitto 2.1 and removed in 3.0, the plugins read their files again on SIGHUP as well.
- Without users nobody can log in, anonymous clients need `allow_anonymous: true` (or `listener_allow_anonymous` of a listener).

### Secrets

`mosquitto_secrets` is a list of entries with `name`, `data` and `target`, the target is the path of the option:

| Target | Passed as |
|---|---|
| `psk_file` | file `/run/secrets/<name>`, the role writes `psk_file /run/secrets/<name>` |
| `listener.<port>.keyfile` | file `/run/secrets/<name>`, the role writes `keyfile` to the listener, for keys that do not come from a realm |
| `connection.<name>.bridge_keyfile` | file `/run/secrets/<name>`, the role writes `bridge_keyfile` to the bridge |
| `connection.<name>.remote_password`, `connection.<name>.local_password`, `connection.<name>.bridge_psk` | value in the section of the bridge, the section is a podman secret |

- The files are mounted with `type=mount`, owned by `1883` with mode `0400`.
- Mosquitto reads the password and the PSK of a bridge only as value of `mosquitto.conf`, there is neither a file option nor an environment variable for them.
  The role writes the whole section of such a bridge with the values to the podman secret `<container name>-bridge-<bridge name>`,
  mounted to `/run/mosquitto/bridges/<bridge name>.conf`, and `mosquitto.conf` ends with `include_dir /run/mosquitto/bridges`.
  The section never exists on the host, `mosquitto.conf` keeps the other bridges and stays readable.
- The secrets are options of the role, they must not be set in `mosquitto_config`. The listeners and bridges of the targets have to exist in `mosquitto_config`.
- A changed secret restarts the running broker.

### Allowed variables

The lists of allowed options and variables prevent unexpected behavior by accident, e.g. a misspelled option that Mosquitto rejects at the start.

- `smarthome_mosquitto__config_allowed`, `smarthome_mosquitto__config_listener_allowed` and `smarthome_mosquitto__config_connection_allowed`
  list the general options, the options of a listener and of a bridge, generated from `man/mosquitto.conf.5.xml` of Mosquitto v2.1.4.
- Set by the role and therefore not allowed: `password_file`, `acl_file`, `plugin`, `global_plugin`, `auth_plugin`, `include_dir` and `per_listener_settings`
  (deprecated since Mosquitto 2.1). Other plugins (e.g. `mosquitto_dynamic_security.so`) are not supported.
- `mosquitto_environment` takes the variables of the image that are no options of Mosquitto, `smarthome_mosquitto__environment_allowed` only lists `UMASK_SET`.
  `PUID` and `PGID` are not allowed, the role writes the files for the user `1883` of the image,
  `MOSQUITTO_PERSISTENCE_LOCATION` is `persistence_location` of `mosquitto_config`.
  Without `mosquitto_environment` the quadlet unit has no environment.

### Container

| Variable | Description |
|---|---|
| `mosquitto_home` | Directory of the configuration and the persistence on the host |
| `mosquitto_ip`, `mosquitto_ipv6` | Addresses of the container in `mosquitto_network` |
| `mosquitto_hostname` | Hostname of the container |
| `mosquitto_timezone` | Time zone of the container |
| `mosquitto_version` | Tag of the image, default `latest` |
| `mosquitto_container` | Merged into the container default, not recursive (e.g. `volumes`, `publish`, `requires`) |
| `mosquitto_autoupdate_enabled`, `mosquitto_autoupdate_schedule` | Updates of the image by `container_update` |
| `mosquitto_realms` | Realms of PKI with local certificates, installed on every start |
| `mosquitto_pki_update_enabled`, `mosquitto_pki_update_schedule` | Restart after the renewal of the certificate of a realm by `pki_update` |

### Validation

Before any change the role checks:

- that `mosquitto_secrets` is a list of entries with name, data and target and unique names,
- the options of `mosquitto_config`, of every listener and every bridge against their allow lists, the options of the role and the secrets,
  that the values are strings, numbers, booleans, null or lists of them without line breaks, and booleans of Mosquitto are booleans,
- that `listener` and `connection` are lists of dictionaries with `port` and `name`, the ports are numbers from 0 to 65535 and unique, the names valid and unique,
- the names of the users, their passwords and the lines of the ACL, an invalid ACL file would stop the broker when it reloads the file,
- the targets of the secrets, the passwords of bridges are strings without line breaks,
- that `mosquitto_realms` is a list of unique names of letters, digits, `_`, `.` and `-`, the realms of listeners and bridges are part of it,
  a listener or bridge with `realm` sets neither certificate nor key itself, and `fullchain.pem` and `privkey.pem` of every realm exist
  (in check mode missing certificates are reported, another role may create them only in a real run),
- the variables of the environment.

### Restart and updates

- A changed `mosquitto.conf`, secret or quadlet unit restarts the running broker, the listeners and bridges are only read at the start.
- Changed users or a changed ACL are reloaded with SIGHUP (`podman kill --signal HUP mosquitto`), the connected clients stay connected.
- The certificates of the realms are installed on every start, the timer of `pki_update` restarts Mosquitto after a renewal.
- Otherwise the service is only started. Updates of the image are done by `container_update` with `mosquitto_autoupdate_enabled`.

### Migration

The role replaces `mosquitto_server`:

| Former variable | New variable |
|---|---|
| `mosquitto_use_podman` | removed, the installation with apt is no longer supported |
| `mosquitto_allow_anonymous` | `mosquitto_config.allow_anonymous` |
| `mosquitto_log_debug`, `mosquitto_log_error`, `mosquitto_log_warning`, `mosquitto_log_notice`, `mosquitto_log_information`, `mosquitto_log_subscribe`, `mosquitto_log_unsubscribe`, `mosquitto_log_websockets` | `mosquitto_config.log_type`, a list of the types, e.g. `[ 'error', 'warning', 'notice', 'information' ]` |
| `mosquitto_persistence` | `mosquitto_config.persistence`, the default is now `true` |
| `mosquitto_tls` | a listener with `port: 8883`, `cafile` and `certfile`, the key as secret with target `listener.8883.keyfile` |
| `mosquitto_acl_topics` | `mosquitto_acl.anonymous`, the lines without `topic` |
| `mosquitto_acl_patterns` | `mosquitto_acl.pattern`, the lines without `pattern` |
| `mosquitto_acl_per_user` | `acl` of the users in `mosquitto_users`, the lines without `topic` |
| `mosquitto_secrets` (users and passwords) | `mosquitto_users` with `password`, `mosquitto_secrets` are now the secrets of the options |
| `mosquitto_bridges` | entries of `mosquitto_config.connection` with `name` instead of `connection`, `remote_password` as secret with target `connection.<name>.remote_password` |

Changed behavior and fixed bugs:

- The passwords were written in plain text to `pwfile` and hashed afterwards with `mosquitto_passwd -U` in the container, errors were ignored.
  The module writes the hashes directly, the password file never contains a plain text password.
- The passwords of bridges were written in plain text to `mosquitto.conf`, they are now only part of a podman secret.
- The users and the ACL are read by the plugins of Mosquitto 2.1 instead of `password_file` and `acl_file`, changes are reloaded with SIGHUP instead of a restart.
- The files are `config/passwd` and `config/acl` instead of `config/pwfile` and `config/aclfile`, the former files and `log/` are not used anymore and can be removed.
- `<mosquitto_home>/config` is mounted read only, `<mosquitto_home>/data` to `/mosquitto/data` instead of the whole home to `/mosquitto`.
- The broker logs to the journal (`log_dest stdout`), persistence is enabled by default.
- The time zone of the container is `mosquitto_timezone`, the former role used `bootstrap_timezone__timezone`.
- `podman___update_mode` is removed, see Restart and updates.
- `mosquitto_realms` (local certificates of PKI realms with `pki_update`) is new.

### Tests

The molecule scenario `default` runs the role in [tart](https://tart.run) VMs on a macOS controller, created by `.molecule/tart/create.yml`.

| Platform | Tested |
|---|---|
| `molecule-mosquitto-default` | only the mandatory variables: default configuration, no users, anonymous and unknown users are refused |
| `molecule-mosquitto` | IPv6, `UMASK_SET`, users with ACL and a pattern, a TLS listener with its key as secret, two listeners with the certificates of the realms `realm1` and `realm2`, a bridge with its password as secret |

`prepare` installs podman, the network and `mosquitto-clients`, creates a CA and a certificate for the address of the broker
self-signed certificates of the realms `realm1` and `realm2` in `/etc/pki/realms`, a certificate of a removed realm in `<mosquitto_home>/certs`
and starts a second broker `molecule-remote` as the other side of the bridge on `molecule-mosquitto`.
`converge` replaces the placeholder of the key secret with the key of `prepare`.

`side_effect` runs the role with invalid values (expect ERROR) and checks the message and that `mosquitto.conf`, `passwd`, `acl` and the quadlet unit are unchanged.
On `molecule-mosquitto` it changes a password: the users are reloaded without a restart, the old password is refused and the new one accepted.
Then it changes `log_type`: the broker restarts. On `molecule-mosquitto-default` a run without a change neither changes nor restarts anything.

`verify` checks the quadlet unit, the files with owner and mode, the hashes of the password file, that no password of the test is part of the files or the unit,
the service, the addresses and the time zone of the container, that the broker refuses anonymous clients and wrong passwords,
a retained message from one user to another, a message the ACL drops, a login over TLS and a message over the bridge to `molecule-remote`.
For the realms it checks the installed certificates (owner, modes, the removed realm), a login over TLS on the listeners of both realms,
the timer of `pki_update` and its certificates, then it renews the certificate of `realm1` with `touch`, runs `pki-update@mosquitto.service`
and checks that Mosquitto restarted and the listener of the realm answers again.

```shell
cd smarthome_mosquitto && MOLECULE_TART_IMAGE='debian' molecule test; cd ..
```
