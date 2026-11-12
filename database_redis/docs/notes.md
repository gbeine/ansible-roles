Redis runs in the container image [redis](https://hub.docker.com/_/redis) (`8-alpine` by default, `redis_version` sets the tag) as podman quadlet.
The entrypoint of the image starts as root, drops the privileges to the user `redis` (uid 999, gid 1000) and loads the modules of the image
(RediSearch, RedisJSON, RedisTimeSeries, RedisBloom). Redis listens on port 6379.
The data directory `<redis_home>/data` is owned by the user `redis` and mounted to `/data`,
the role writes `<redis_home>/redis.conf` and the ACL file `<redis_home>/users.acl` and mounts them read only.

### Configuration

Redis is configured with the dictionary `redis_config`, merged over the default of the role (`bind: '* -::*'` and `port: 6379`).
Every key is an option of `redis.conf`, see the [configuration of Redis](https://redis.io/docs/latest/operate/oss_and_stack/management/config/):

- a string or a number writes `option value`, an empty string writes `option ""`
- a list writes one line per element, e.g. for `save`, `rename-command` or `loadmodule`
- `false` or `null` removes the option, e.g. an option of the default
- `true` is rejected, Redis options need a value, e.g. `'yes'`

```yaml
redis_config:
  maxmemory: '256mb'
  maxmemory-policy: 'allkeys-lru'
  appendonly: 'yes'
  save:
    - '3600 1'
    - '300 100'
  databases: 4
```

The role writes `daemonize no`, `dir /data` and `aclfile /etc/redis/users.acl` before the options of `redis_config`,
these options, `include`, `user` and `requirepass` must not be set in `redis_config`.
Options of the modules, e.g. `search-timeout` or `ts-retention-policy`, are set in `redis_config` as well.

### Users

The users are ACL users of Redis, defined in `redis_users` with `name`, `rules` and `enabled`, their passwords in `redis_passwords`:

```yaml
redis_users:
  - name: 'default'
    rules: [ '~*', '&*', '+@all' ]
  - name: 'nextcloud'
    rules: [ '~nextcloud:*', '+@all', '-@dangerous' ]
  - name: 'monitoring'
    rules: [ '+ping', '+info' ]
    enabled: false
redis_passwords:
  default: "{{ vault_redis_default_password }}"
  nextcloud: "{{ vault_redis_nextcloud_password }}"
  monitoring: "{{ vault_redis_monitoring_password }}"
```

`rules` is a list of [ACL rules](https://redis.io/docs/latest/operate/oss_and_stack/management/security/acl/),
one rule per element, spaces are only allowed in selectors in parentheses, e.g. `'(~log:* +get)'`.
The role writes every user as `user <name> reset <rules> on|off #<SHA-256 of the password>`,
`reset` starts the user without permissions, `enabled: false` writes `off`.
Passwords are only stored as SHA-256 in the ACL file, they are never written in plain text.
Rules with passwords (`>`, `<`, `#`, `!`), `nopass`, `on` and `off` are rejected, the passwords are set with `redis_passwords`, on and off with `enabled`.

Every user needs a password in `redis_passwords`, except the user `default`.
Without an entry for `default` in `redis_users` the role writes the default of Redis, `user default on nopass sanitize-payload ~* &* +@all`:
every connection is authenticated as `default` without password, like before.
To require a password for every connection, add `default` with a password to `redis_users` and `redis_passwords`,
clients then need the user and the password, e.g. `redis://default:<password>@host:6379/0`.

### Databases

Redis has no named databases, only numbered ones from 0 to `databases` - 1 (16 by default), they always exist and need not be created.
`redis_config.databases` sets the number. Redis has no permissions per database,
users are restricted to their keys by key patterns in `rules`, e.g. `~nextcloud:*`, so several applications can share a database with prefixes.

### Secrets

Options of `redis.conf` carrying a password are set with `redis_secrets`, a list of podman secrets with `name`, `data` and `target`.
Allowed targets are `masterauth` (password for replication from a primary), `tls-key-file-pass` and `tls-client-key-file-pass`.
The role creates every secret with the line `<target> "<data>"`, mounts it to `/run/secrets/<name>` for the user of the image
and includes it at the end of `redis.conf` with `include /run/secrets/<name>`, so the password is neither in `redis.conf` nor in the environment.
A changed secret restarts the running service.

```yaml
redis_config:
  replicaof: '192.168.99.30 6379'
  masteruser: 'replication'
redis_secrets:
  - name: 'redis_masterauth'
    data: "{{ vault_redis_masterauth }}"
    target: 'masterauth'
```

### Allowed variables

The role only allows the options in `database_redis__config_allowed` and the secrets with a target in `database_redis__secrets_allowed`,
it stops before any change if unknown options or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option that has to be passed as secret.

The allowed options are generated from `src/config.c` of [Redis](https://github.com/redis/redis) 8.10.3, without the hidden options,
plus `rename-command` and `loadmodule`, and from the configurations of RediSearch, RedisTimeSeries and RedisBloom v8.10.1, the modules of the image.
Former names of options, e.g. `slaveof`, are rejected together with the current name, e.g. `replicaof`.
New versions of Redis may add options, the list is generated again.

The environment of the container only allows the variables of `docker-entrypoint.sh` of the image, `SKIP_FIX_PERMS` and `SKIP_DROP_PRIVS`,
set with `redis_environment`. The check uses the container after merging `redis_container`, so `redis_container.environment` is checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `redis_container`, it is merged over the default of the container.
The merge is not recursive, `redis_container.volumes` replaces the data directory, `redis.conf` and the ACL file,
`redis_container.command` replaces the start of `redis-server` with `redis.conf`.
After the start the role waits until the port of `redis_config.port` is open, so roles depending on Redis can use it.

### Validation

The role checks before any change:

- `redis_container` and `redis_config` are dictionaries, merging them with the default fails otherwise
- `redis_secrets` is a list of entries with `name`, `data` and `target`, unique names and data without line breaks
- the options of `redis_config` are known, are neither set by the role nor passwords, have no former name, are no `true`, contain no line breaks
  and the port is a number
- `redis_users` is a list of entries with unique and valid names, rules as list without passwords, `nopass`, `on` and `off`, `enabled` as boolean,
  every user except `default` has a password in `redis_passwords`, `redis_passwords` has no passwords of unknown users and no empty passwords
- only allowed environment variables and secrets are set in the container

A failing template in the variables, e.g. an unknown filter, stops the role before anything changes.

### Restart and updates

Redis is restarted if it was running and a secret, the quadlet unit, `redis.conf` or the ACL file changed, otherwise it is started and enabled.
On the restart Redis saves the data if `save` or `appendonly` is configured, the default of Redis saves snapshots.
Updates of the image are done by `container_update` with `redis_autoupdate_enabled: true` and `redis_autoupdate_schedule`,
without `redis_autoupdate_schedule` the schedule of `container_update` is used.

### Multiple instances

`tasks/loop.yml` runs the role for every entry in `redis_instances`.
Every entry takes the variables without the prefix `redis_`, e.g. `home`, `ip`, `config`, `users`, `passwords` and `secrets`,
missing keys fall back to the defaults of the role.
Every instance needs its own container name (`container.name`) and its own secret names.

Include `tasks/loop.yml` in the play instead of the role:

```yaml
- name: 'Configure host.example.org'
  become: 'yes'
  hosts: 'host23'
  tasks:
    - tags: [ 'database_redis' ]
      ansible.builtin.include_tasks:
        file: 'roles/database_redis/tasks/loop.yml'
```

The instances are defined in `redis_instances`, e.g. in the host variables:

```yaml
redis_instances:
  - home: '/srv/container/redis-cache'
    hostname: 'redis-cache'
    ip: '192.168.99.41'
    network: 'podman99'
    timezone: 'Europe/Berlin'
    container:
      name: 'redis-cache'
    config:
      maxmemory: '256mb'
      maxmemory-policy: 'allkeys-lru'
      save: ''
  - home: '/srv/container/redis-queue'
    hostname: 'redis-queue'
    ip: '192.168.99.42'
    network: 'podman99'
    timezone: 'Europe/Berlin'
    container:
      name: 'redis-queue'
    config:
      appendonly: 'yes'
    users:
      - name: 'default'
        rules: [ '~*', '&*', '+@all' ]
    passwords:
      default: "{{ vault_redis_queue_password }}"
```

### Migration

- `redis_config` was a string, written to `<redis_home>/data/redis.conf`, but never passed to `redis-server`, Redis always ran with its defaults.
  Now `redis_config` is a dictionary of options and Redis reads `<redis_home>/redis.conf`, convert the former string, e.g. `maxmemory 64mb` to `maxmemory: '64mb'`.
  The role removes the unused `<redis_home>/data/redis.conf`.
- `redis_port` is replaced by `redis_config.port`, `redis_podman_tag` by `redis_version`.
- `redis_use_podman` was never evaluated and is removed.
- The user `default` stays without password, users and passwords are new with `redis_users` and `redis_passwords`.
- `/etc/localtime` and `/etc/timezone` are not mounted anymore, the timezone is set with the timezone of the container.
- `podman___update_mode` is not evaluated anymore, the role neither stops the container nor pulls the image or recreates the container.
- `tasks/loop.yml` takes all variables of the role, missing keys fall back to the defaults instead of failing.
- The tag `database_redis` stays, the tag `database` is added.

### Tests

The molecule scenarios run the role in [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

The scenario `default` uses two VMs:

| Platform | Test case |
|---|---|
| `molecule-redis-default` | Only the mandatory variables, the user `default` without password |
| `molecule-redis` | IPv6, labels, options with a list, the users `default` and `app` with passwords, a disabled user and the secret `masterauth` with a backslash and a double quote |

`prepare` creates the podman network and pulls the image of Redis.
`side_effect` runs the role with `redis_container` and `redis_config` no dictionaries, an unknown option, the former name `slaveof`,
the option `dir` set by the role, `requirepass`, `masterauth` in `redis_config`, `true` as value, a secret without `target`, an unknown secret,
a user without password, a password in the rules of a user and an unknown environment variable in `redis_container.environment`
and checks that it fails with the expected message and the quadlet unit, `redis.conf` and the ACL file are unchanged (tasks marked `expect ERROR`),
then it waits until Redis answers on `molecule-redis`, shows the log of the service otherwise, and changes `maxmemory`,
`redis.conf` changes and Redis has to restart.
`verify` checks the quadlet unit with the command, the volumes and the mounted secret, the service and the addresses of the container,
the owner and the permissions of the files, the lines of `redis.conf` and the ACL file without passwords in plain text and the removed file of the former role.
With `redis-cli` in the container it checks `PING` without password, on `molecule-redis` it has to fail,
the number of databases, `masterauth` read from the secret and the loaded module `search` as the user `default`,
that the user `app` may write its keys `app:*` but neither other keys nor `FLUSHALL` and that the disabled user cannot authenticate.

The scenario `loop` deploys two instances with `tasks/loop.yml` in the VM `molecule-redis-loop`, `redis-cache` with IPv4 only and `redis-queue` with IPv6
and the user `default` with password. `verify` checks every instance: the addresses, the files and that every quadlet unit only contains its own secret,
`redis.conf`, the service, `PING` and `masterauth` read from the secret of the instance.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_redis
MOLECULE_TART_IMAGE='debian' molecule test --all
```
