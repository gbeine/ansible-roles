Icinga Web 2 runs in the official container image [icinga/icingaweb2](https://hub.docker.com/r/icinga/icingaweb2) as podman quadlet,
it listens on port 8080. The role mounts only the configuration and the state of Icinga Web, everything else of `/data` comes from the image:

| Host | Container |
|---|---|
| `<icingaweb_home>/etc` | `/data/etc/icingaweb2` (configuration) |
| `<icingaweb_home>/lib` | `/data/var/lib/icingaweb2` (state) |

### Configuration

`icingaweb_config` contains the INI files of Icinga Web: the file without `.ini` (e.g. `resources` or `modules/icingadb/redis`),
the section and the option. It is merged recursively over the default of the role, `null` removes a file, a section or an option.
The role writes the files to `<icingaweb_home>/etc` like Icinga Web writes them: values are quoted and escaped,
booleans are `1` and `0`, lists are joined by commas.

```yaml
icingaweb_config:
  config:
    logging:
      level: 'WARNING'
  roles:
    Viewers:
      groups: 'viewers'
      permissions: 'module/icingadb'
      icingadb/filter/objects: 'host.vars.team=ops'
  resources:
    icingaweb_db:
      host: 'mariadb'
    icingadb:
      host: 'mariadb'
  modules/icingadb/redis:
    redis1:
      host: 'redis-icingadb'
  modules/icingadb/commandtransports:
    icinga2:
      host: 'icinga-master'
      username: 'icingaweb'
```

`resources.icingaweb_db.host`, `resources.icingadb.host`, `modules/icingadb/redis.redis1.host`,
`modules/icingadb/commandtransports.icinga2.host` and `modules/icingadb/commandtransports.icinga2.username` are mandatory.

The default of the role:

```yaml
config:
  global:
    config_resource: 'icingaweb_db'
  logging:
    log: 'php'
authentication:
  icingaweb2:
    backend: 'db'
    resource: 'icingaweb_db'
groups:
  icingaweb2:
    backend: 'db'
    resource: 'icingaweb_db'
roles:
  Administrators:
    users: 'icingaadmin'
    permissions: '*'
    groups: 'Administrators'
resources:
  icingaweb_db: { type: 'db', db: 'mysql', dbname: 'icingaweb', username: 'icingaweb', charset: 'utf8mb4' }
  icingadb: { type: 'db', db: 'mysql', dbname: 'icinga', username: 'icingaweb', charset: 'utf8mb4' }
modules/icingadb/config:
  icingadb:
    resource: 'icingadb'
modules/icingadb/redis:
  redis1:
    port: 6379
modules/icingadb/commandtransports:
  icinga2:
    transport: 'api'
```

`icingaweb_modules` lists the enabled modules (default `[ 'icingadb' ]`), the entrypoint of the image links them in `enabledModules`.

### Secrets

The INI files of Icinga Web cannot read files and the image reads no `*_FILE` variables.
The entrypoint of the image would write the passwords of `icingaweb.*` variables in plain text to `/data/etc/icingaweb2` on the host.
So the files with passwords are podman secrets:

- the `target` of an entry of `icingaweb_secrets` is `<file>.<section>.<option>` of a password, the passwords of
  `monitoring_icinga_web__config_secret_options` are `password` and `bind_pw` of `resources`, `password` of `modules/icingadb/redis`
  and `password` of `modules/icingadb/commandtransports`, the section has to be part of `icingaweb_config`
- the role merges the passwords into the file, renders the whole file as podman secret `<container name>-<file>`
  (e.g. `icingaweb-resources`, `icingaweb-modules-icingadb-redis`) and mounts it to `/data/etc/icingaweb2/<file>.ini`
  with `uid=33,gid=33,mode=0400`, the file never exists on the host (podman leaves an empty mount point)
- the passwords of `resources.icingaweb_db` and `resources.icingadb` are mandatory

The users of a database authentication backend are created by the entrypoint of the image at every start, it reads their passwords from the environment only.
A secret with the target `passwords.<backend>.<user>`, e.g. `passwords.icingaweb2.icingaadmin`,
is passed with `type=env,target=icingaweb.passwords.<backend>.<user>`.

```yaml
icingaweb_secrets:
  - name: 'icingaweb_db_password'
    data: "{{ vault_icingaweb_db_password }}"
    target: 'resources.icingaweb_db.password'
  - name: 'icingaweb_icingadb_password'
    data: "{{ vault_icingaweb_icingadb_password }}"
    target: 'resources.icingadb.password'
  - name: 'icingaweb_api_password'
    data: "{{ vault_icinga_api_icingaweb2 }}"
    target: 'modules/icingadb/commandtransports.icinga2.password'
  - name: 'icingaweb_admin_password'
    data: "{{ vault_icingaweb_admin_password }}"
    target: 'passwords.icingaweb2.icingaadmin'
```

### Allowed variables

The role only allows the files, sections and options of `monitoring_icinga_web__config_allowed`, the passwords of `monitoring_icinga_web__config_secret_options`
and the environment variables in `monitoring_icinga_web__environment_allowed`, it stops before any change if unknown files, options, secrets or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo or a password that has to be passed as secret.
The lists are generated from the forms of Icinga Web v2.14.1 and Icinga DB Web v1.5.0, the sections of most files are names (`*`),
`roles` also takes the restrictions of the modules, e.g. `icingadb/filter/objects`.

`icingaweb_environment` has no default and only takes `ICINGAWEB_SERIALIZER_COMPAT` of the entrypoint,
the options of Icinga Web (`icingaweb.*`) are rejected, the entrypoint would overwrite the files of the role.
The role sets `icingaweb.enabledModules` from `icingaweb_modules`.
The check of the environment uses the environment of the container after merging `icingaweb_container`.

### Container

Ports, volumes, labels, additional hosts (`etc_hosts`) and dependencies are changed with `icingaweb_container`, it is merged over the default of the container.
The merge is not recursive, `publish` and `volumes` replace the values of the default completely,
`icingaweb_container.environment` replaces the environment including `icingaweb_environment` and the modules.
The dependencies of the quadlet unit are lists of units in `icingaweb_container`: `requires`, `wants`, `after`, `part_of` and `binds_to`
are written as `Requires=`, `Wants=`, `After=`, `PartOf=` and `BindsTo=` to `[Unit]`.

```yaml
icingaweb_container:
  wants: [ 'mariadb.service' ]
  after: [ 'mariadb.service' ]
```

### Validation

The role checks before any change:

- `icingaweb_secrets` is a list of entries with `name`, `data` and `target` and unique names, every target is a known password of an existing section
  or `passwords.<backend>.<user>` and set once, the passwords of both resources are set, the names start with a letter or digit,
  the data are strings without line breaks
- `icingaweb_config` contains known files and options, the files and sections are dictionaries, no passwords,
  the mandatory options and values without line breaks
- `icingaweb_modules` is a list of names of modules
- the former single variables of the role are not set, the message names their replacement
- `icingaweb_environment`, if set, is a dictionary without options of Icinga Web and line breaks, only allowed environment variables are set in the container

If `icingaweb_container` or `icingaweb_config` is no dictionary, merging it with the default fails before anything changes.

### Restart and updates

Icinga Web is restarted if it was running and a file of the configuration, a secret or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role shows the journal of the service.
The entrypoint imports the schema into the empty database of the authentication backend and creates the users before Apache starts,
the role waits until the login page answers and shows the journal otherwise.
Updates of the image are done by `container_update` with `icingaweb_autoupdate_enabled: true` and `icingaweb_autoupdate_schedule`,
without `icingaweb_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former version of the role configured Icinga Web with single variables in `icingaweb.*` variables of the environment,
they are options of `icingaweb_config` and secrets now. The role rejects the former variables and names their replacement.

| Former variable | Replacement |
|---|---|
| `icingaweb_admin_password` | secret with target `passwords.icingaweb2.icingaadmin` |
| `icingaweb_redis_host`, `icingaweb_redis_port` | `host`, `port` of `modules/icingadb/redis.redis1` |
| `icingaweb_icinga_host`, `icingaweb_icinga_user` | `host`, `username` of `modules/icingadb/commandtransports.icinga2` |
| `icingaweb_icinga_password` | secret with target `modules/icingadb/commandtransports.icinga2.password` |
| `icingaweb_db_host`, `icingaweb_db_name`, `icingaweb_db_user` | `host`, `dbname`, `username` of `resources.icingaweb_db` |
| `icingaweb_db_pass` | secret with target `resources.icingaweb_db.password` |
| `icingaweb_icingadb_host`, `icingaweb_icingadb_name`, `icingaweb_icingadb_user` | `host`, `dbname`, `username` of `resources.icingadb` |
| `icingaweb_icingadb_pass` | secret with target `resources.icingadb.password` |
| `podman___update_mode` | `icingaweb_autoupdate_enabled` |

Changed behavior:

- the fixed secrets `icingaweb_admin_password`, `icingaweb_icinga_password`, `icingaweb_db_password` and `icingaweb_icingadb_password` are replaced by `icingaweb_secrets`,
  the names are chosen freely, the old secrets are not removed
- the passwords are no longer written to `/data/etc/icingaweb2/resources.ini` and `modules/icingadb/commandtransports.ini` on the host,
  the role removes these files of the former versions before it mounts the secrets
- `config_backend` of `config.global` is not set anymore, Icinga Web v2.14 stores the preferences in `config_resource`
- the modules are set with `icingaweb_modules`, all options of the files of Icinga Web can be set with `icingaweb_config`
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the time zone is set with `icingaweb_timezone`
- Icinga Web is restarted if the configuration or a secret changed, the role waits until the login page answers
- the tags are `monitoring` and `monitoring_icinga_web`
- `<icingaweb_home>/data` is not mounted to `/data` anymore, the directories on the host are `etc` and `lib`, the role does not move the files of former versions.
  Move them before the first run and remove `<icingaweb_home>/data` afterwards:
  `mv <icingaweb_home>/data/etc/icingaweb2 <icingaweb_home>/etc`, `mv <icingaweb_home>/data/var/lib/icingaweb2 <icingaweb_home>/lib`

### Tests

The molecule scenario `default` uses tart with the VMs `molecule-icingaweb-default` with the mandatory variables
and `molecule-icingaweb` with the options and Redis with a password.
`prepare` starts MariaDB with the databases `icingaweb` and `icinga` and Redis as containers, Icinga 2 is not needed.
`side_effect` runs the role with `icingaweb_container` and `icingaweb_config` not a dictionary, an unknown file, an unknown option, an unknown section of `config`,
a password in `icingaweb_config`, without the host of Redis, a secret without target, an unknown secret, the secret of a missing section,
without the password of the database of Icinga Web, a former variable, an option in `icingaweb_environment`
and an unknown variable in `icingaweb_container.environment` and checks that it fails with the expected message
and the quadlet unit and `config.ini` are unchanged (tasks marked `expect ERROR`),
then it changes `config.logging.level` on `molecule-icingaweb`, `config.ini` changes and Icinga Web has to restart.
`verify` checks the quadlet unit with the mounted files and the secrets of the users and without passwords, the lines of the files on the host,
that the files with passwords are not on the host and no file on the host contains a password, the files with passwords in the container,
the service and logs in as `icingaadmin` with the login form.

```shell
cd monitoring_icinga_web
MOLECULE_TART_IMAGE='debian' molecule test
```
