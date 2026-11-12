InfluxDB runs in the official container image [influxdb](https://hub.docker.com/_/influxdb) as podman quadlet,
the role supports InfluxDB 1.x and 2.x and manages their databases, buckets and users.
InfluxDB 3 Core is installed with the role `database_influxdb_core`.

### Releases

The release is selected with `influxdb_release`, the default is `2.9`. `influxdb_version` is the tag of the image,
the default is `<release>-alpine`, a tag has to start with the release, e.g. `2.9.1-alpine`.

| `influxdb_release` | Version of the image | User of the image | Data in the container |
|---|---|---|---|
| `1.11`, `1.12`, `1.13` | 1.11.8, 1.12.4, 1.13.2 | `influxdb` (1500), runs as this user | `/var/lib/influxdb` |
| `2.7`, `2.8`, `2.9` | 2.7.12, 2.8.0, 2.9.1 | `influxdb` (1000), the entrypoint starts as root and changes to this user | `/etc/influxdb2`, `/var/lib/influxdb2` |

The values of the major version (user of the image, volumes, defaults of the environment and secrets) are in `vars/influxdb1.yml` and `vars/influxdb2.yml`,
the allowed variables of every release in `vars/environment-<release>.yml`, the role includes both before it checks anything.
The major version also selects the management of databases and users in `tasks/influxdb1.yml` or `tasks/influxdb2.yml`. Data of InfluxDB 1.x cannot be used by 2.x, the upgrade of the image
(`DOCKER_INFLUXDB_INIT_MODE: upgrade`) is not supported by the role.

### Configuration

InfluxDB is configured with environment variables in `influxdb_environment`, merged over the default of the major version:

- InfluxDB 1.x reads every option of `influxdb.conf` as `INFLUXDB_<SECTION>_<KEY>`, e.g. `INFLUXDB_LOGGING_LEVEL`,
  the sections `graphite`, `collectd`, `opentsdb` and `udp` are lists, the first entry is set with index 0, e.g. `INFLUXDB_GRAPHITE_0_ENABLED`.
  The default sets `INFLUXDB_HTTP_AUTH_ENABLED: 'true'` and `INFLUXDB_ADMIN_USER: 'admin'`, the role needs the admin to manage databases and users.
- InfluxDB 2.x reads every flag of `influxd` as `INFLUXD_<FLAG>`, e.g. `INFLUXD_LOG_LEVEL`.
  The default sets `DOCKER_INFLUXDB_INIT_MODE: 'setup'`, `DOCKER_INFLUXDB_INIT_USERNAME: 'admin'` and `DOCKER_INFLUXDB_INIT_BUCKET: 'default'`,
  `DOCKER_INFLUXDB_INIT_ORG` is mandatory. The setup creates the admin, the organization, the bucket and the admin token on the first start.

```yaml
influxdb_environment:
  DOCKER_INFLUXDB_INIT_ORG: 'example'
  DOCKER_INFLUXDB_INIT_RETENTION: '52w'
  INFLUXD_LOG_LEVEL: 'warn'
```

Values are strings, e.g. `'true'`. The variables of the setup only have an effect on the first start.

### Databases, buckets and users

The role manages databases (1.x) or buckets (2.x) and users over the HTTP API of InfluxDB after every start,
authenticated as the admin of the image. Databases, buckets, users and privileges that are not listed are not changed.
The passwords of the users are set in `influxdb_passwords`, a user whose password does not work gets the password of `influxdb_passwords`.
The admin of the image is not part of `influxdb_users`, its password is the secret of the admin.
The retention is a duration like `30d`, `12h` or `1w2d`, `INF` or `0` keeps the data infinitely.

InfluxDB 1.x:

```yaml
influxdb_release: '1.13'
influxdb_databases:
  - name: 'telegraf'
    retention: '30d'
  - name: 'app'
influxdb_users:
  - name: 'telegraf'
    grants:
      - { database: 'telegraf', privilege: 'WRITE' }
  - name: 'grafana'
    grants:
      - { database: 'telegraf', privilege: 'READ' }
      - { database: 'app', privilege: 'READ' }
  - name: 'operator'
    admin: true
influxdb_passwords:
  telegraf: "{{ vault_influxdb_telegraf_password }}"
  grafana: "{{ vault_influxdb_grafana_password }}"
  operator: "{{ vault_influxdb_operator_password }}"
```

The retention changes the default retention policy of the database, the shard duration follows the rules of InfluxDB for new policies.
`privilege` is `READ`, `WRITE` or `ALL`, the role grants the privileges of `grants` and revokes the privileges on other databases.
`admin: true` grants all privileges, `admin: false` (the default) revokes them.

InfluxDB 2.x:

```yaml
influxdb_buckets:
  - name: 'telegraf'
    retention: '30d'
  - name: 'logs'
    org: 'operations'
influxdb_users:
  - name: 'grafana'
  - name: 'operator'
    role: 'owner'
influxdb_passwords:
  grafana: "{{ vault_influxdb_grafana_password }}"
  operator: "{{ vault_influxdb_operator_password }}"
```

`org` is the organization of a bucket or user, the default is the organization of the setup, missing organizations are created.
`role` is `member` (the default) or `owner` of the organization of the user. InfluxDB knows only one role per user and organization,
the role changes it if needed, memberships in other organizations are kept.
Applications usually write and read with tokens, InfluxDB 2.x creates tokens with generated values, they are not managed by the role.

### Secrets

`influxdb_secrets` is a list of podman secrets with `name`, `data` and `target`, the name of the environment variable.
Neither a target nor its file variable may be set in `influxdb_environment`.

InfluxDB 2.x reads the password and the token of the setup from files, the role mounts the secrets to `/run/secrets/<name>`
for the user of the image and sets the file variables:

| Target | File variable | |
|---|---|---|
| `DOCKER_INFLUXDB_INIT_PASSWORD` | `DOCKER_INFLUXDB_INIT_PASSWORD_FILE` | mandatory |
| `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN` | `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN_FILE` | mandatory, used by the role and by `backup_influxdb` |
| `INFLUXD_VAULT_TOKEN` | - | passed in the environment, `influxd` reads it only from there |

The image of InfluxDB 1.x reads no secret from a file, `init-influxdb.sh` and `influxd` only read the environment,
so the secrets of 1.x are passed with `type=env`:

| Target | |
|---|---|
| `INFLUXDB_ADMIN_PASSWORD` | mandatory, without it `init-influxdb.sh` writes a random password to the log |
| `INFLUXDB_HTTP_SHARED_SECRET` | optional, the secret of JWT tokens |

```yaml
influxdb_secrets:
  - name: 'influxdb_password'
    data: "{{ vault_influxdb_password }}"
    target: 'DOCKER_INFLUXDB_INIT_PASSWORD'
  - name: 'influxdb_admin_token'
    data: "{{ vault_influxdb_admin_token }}"
    target: 'DOCKER_INFLUXDB_INIT_ADMIN_TOKEN'
```

The password and the token of the setup only have an effect on the first start, the role uses them to manage the buckets and users,
so they have to stay the values of the setup.

### Allowed variables

The role only allows the variables of the release in `vars/environment-<release>.yml` and the secrets of the major version,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo, a variable of the other major version or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `influxdb_container`,
so variables set with `influxdb_container.environment` are checked as well.

The lists are generated from `etc/config.sample.toml` of InfluxDB 1.x and from the flags in `cmd/influxd/launcher/cmd.go` of InfluxDB 2.x
of the version of the image, without the testing flags of 2.x, plus the variables of the entrypoint of the image.
The users of `init-influxdb.sh` of 1.x (`INFLUXDB_DB`, `INFLUXDB_USER`, `INFLUXDB_WRITE_USER`, `INFLUXDB_READ_USER` and their passwords) are rejected,
databases and users are managed with `influxdb_databases`, `influxdb_users` and `influxdb_passwords`.

### Container

The container `influxdb` mounts `<influxdb_home>/data` and `<influxdb_home>/backup` to `/backup`, 2.x also `<influxdb_home>/etc` to `/etc/influxdb2`.
`backup_influxdb` uses the container `influxdb`, the admin token and the backup directory.
Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `influxdb_container`, it is merged over the default of the container.
The merge is not recursive, `influxdb_container.environment` replaces the environment including `influxdb_environment`, use `influxdb_environment` instead.
InfluxDB listens on port 8086, the port and HTTPS follow `INFLUXDB_HTTP_BIND_ADDRESS` and `INFLUXDB_HTTP_HTTPS_ENABLED` (1.x)
or `INFLUXD_HTTP_BIND_ADDRESS` and `INFLUXD_TLS_CERT` (2.x), the role uses them to reach the API on the address of the container.

### Validation

The role checks before any change:

- `influxdb_release` is supported and `influxdb_version` starts with the release
- `influxdb_secrets` is a list of entries with `name`, `data` and `target` and unique names, the mandatory secrets exist
- the mandatory variables are set, `INFLUXDB_HTTP_AUTH_ENABLED` is `true` (1.x), `DOCKER_INFLUXDB_INIT_MODE` is `setup` (2.x),
  the users of the image are not set, neither a secret nor its file variable is set in `influxdb_environment`
- `influxdb_databases`, `influxdb_buckets` and `influxdb_users` are lists of entries with unique and valid names and valid retentions,
  databases only with 1.x, buckets only with 2.x, `admin` and `grants` only with 1.x, `org` and `role` only with 2.x,
  privileges and roles are known, grants only on databases of `influxdb_databases`, the admin is not in `influxdb_users`
- every user has a password in `influxdb_passwords`, `influxdb_passwords` has no passwords of unknown users and no empty passwords
- only allowed environment variables and secrets are set in the container

If `influxdb_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

InfluxDB is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `influxdb_environment`, otherwise it is started and enabled.
The role waits until `/ping` answers, shows the log of the service otherwise, and manages the databases, buckets and users afterwards.
Updates of the image are done by `container_update` with `influxdb_autoupdate_enabled: true` and `influxdb_autoupdate_schedule`,
without `influxdb_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former role installed InfluxDB 2 or InfluxDB 3 Core with `influxdb_version` (2 or 3):

- InfluxDB 3 Core is installed with the role `database_influxdb_core`.
- `influxdb_version: 2` is replaced by `influxdb_release`, e.g. `2.9`, `influxdb_version` is the tag of the image now, `influxdb_tag` is removed.
- `influxdb_username`, `influxdb_org`, `influxdb_bucket` and `influxdb_retention` are replaced by `DOCKER_INFLUXDB_INIT_USERNAME`, `DOCKER_INFLUXDB_INIT_ORG`,
  `DOCKER_INFLUXDB_INIT_BUCKET` and `DOCKER_INFLUXDB_INIT_RETENTION` in `influxdb_environment`.
- `influxdb_password` and `influxdb_admin_token` are replaced by the secrets `DOCKER_INFLUXDB_INIT_PASSWORD` and `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN`,
  they are mounted as files instead of the environment, keep the former values, the role uses the token.
- `influxdb_expose` and `influxdb_publish` are removed, the port 8086 is not published by default anymore, set `influxdb_container.publish` if needed.
- `influxdb_use_podman` is removed, the handler `Restart InfluxDB container` is removed.
- The directories `etc`, `data` and `backup` of `influxdb_home` stay.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the timezone is set with `TZ` and the timezone of the container.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- Buckets and users are new with `influxdb_buckets`, `influxdb_users` and `influxdb_passwords`, InfluxDB 1.x is new.
- The tag `database_influxdb` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in three [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
Three platforms instead of two test both major versions. The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-influxdb-default` | InfluxDB 2.9 with the mandatory variables, the organization of the setup and the secrets of the setup |
| `molecule-influxdb` | InfluxDB 2.9 with IPv6, labels, `INFLUXD_LOG_LEVEL`, buckets with retention, a second organization, a member and an owner |
| `molecule-influxdb-1` | InfluxDB 1.13 with databases with retention, users with `WRITE`, `READ` and `ALL`, an admin and a password with a single quote |

`prepare` creates the podman network and pulls the images.
`side_effect` runs the role with `influxdb_container` not a dictionary, InfluxDB 3, the former major version as tag, a variable of the other major version,
a secret without `target`, without the secrets of the admin, the password of the admin in the environment, a user without password, the admin in the users,
an unknown secret, the upgrade mode and databases with 2.9, InfluxDB 1.13 without authentication, with a user of the image,
with a grant on an unknown database, with an unknown privilege and with an invalid retention,
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`).
On `molecule-influxdb` and `molecule-influxdb-1` it changes the log level, adds a bucket or database and changes a password,
the service has to restart and the role has to create the bucket or database and change the password.
`verify` checks the quadlet unit with the volumes and the secrets without passwords, the service, the addresses and the environment of the container,
the owner of the data directory and `/ping`.
For 2.x it checks the buckets and their retention, the sign in of the users with their passwords and with a wrong password,
the owners of the organization and writes and queries a point with the admin token.
For 1.x it checks the databases and their retention, the admins and that `writer` may only write, `reader` only read from `telegraf`
and write to `app`, and that a wrong password is rejected.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_influxdb
MOLECULE_TART_IMAGE='debian' molecule test
```
