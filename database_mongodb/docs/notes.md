MongoDB runs in the official container image [mongo](https://hub.docker.com/_/mongo) as podman quadlet, the role manages its accounts and the replica set.
`mongodb_release` selects the major version (`8.0` by default, `7.0`, `8.3` and `9.0` are supported), `mongodb_version` is the tag of the image
and has to start with the release, e.g. `8.0.38`. The release selects the allowed options and server parameters.
MongoDB runs as the user `mongodb` (uid and gid 999) of the image, the databases are in `<mongodb_home>/db`, mongod.conf in `<mongodb_home>/etc`.
MongoDB listens on port 27017 of the address of the container.

### Configuration

The role writes `<mongodb_home>/etc/mongod.conf` and starts `mongod --config /etc/mongo/mongod.conf`.
`mongodb_config` is a dictionary of the sections of the [configuration file](https://www.mongodb.com/docs/manual/reference/configuration-options/),
it is merged recursively over the default of the role.

- a dictionary is a section, e.g. `storage.wiredTiger.engineConfig`
- a string, a number, a boolean or a list is written as value of the option
- `null` removes the option

mongod.conf is YAML, booleans are values of the options (e.g. `net.ipv6: false`), so `false` does not remove an option like in the roles writing `key=value` files.

```yaml
mongodb_config:
  operationProfiling:
    slowOpThresholdMs: 200
  storage:
    wiredTiger:
      engineConfig:
        cacheSizeGB: 1
  setParameter:
    diagnosticDataCollectionEnabled: false
```

The role sets the options the image, the initialization and the role depend on, they must not be set in `mongodb_config`:
`net.port`, `net.bindIp`, `net.bindIpAll`, `storage.dbPath`, `security.authorization`, `security.keyFile` and `processManagement.fork`.
Passwords (`net.tls.certificateKeyFilePassword`, `net.tls.clusterPassword`) must not be written to mongod.conf.

### Initialization

The image initializes MongoDB only on an empty `/data/db`: its entrypoint starts a temporary `mongod` bound to 127.0.0.1 without authorization,
creates the user `mongodb_root_username` (`root` by default) with the role `root` in `admin`, stops the temporary `mongod` and starts `mongod`.

The role runs the initialization exactly once in its own container `mongodb-init`:

- the role looks for the files `WiredTiger`, `journal`, `local.0` and `storage.bson` in `<mongodb_home>/db` like the entrypoint does
- without them it starts `mongodb-init` without network, with the volumes and mongod.conf of MongoDB,
  `MONGO_INITDB_ROOT_USERNAME` and the root password as file in `MONGO_INITDB_ROOT_PASSWORD_FILE`
- it waits for the message `MongoDB init process complete` of the entrypoint and removes `mongodb-init` afterwards, also if the initialization failed

The quadlet unit of MongoDB never contains the variables of the initialization or the root password, the entrypoint only adds `--auth`
with the variables of the initialization, so the role sets `security.authorization: enabled` in mongod.conf.
If the initialization fails, the content of `<mongodb_home>/db` has to be removed before the next run, an initialization only runs on an empty directory.

### Replica set

If `mongodb_config.replication.replSetName` is set, the role initiates a replica set with the address of the container
(`<mongodb_ip>:27017`) as the only member and waits for its primary. Applications reading the oplog (e.g. Rocket.Chat) need a replica set.
A replica set with authorization needs a keyfile for the internal authentication, the secret `MONGO_KEYFILE` is mandatory then.
The role initiates the replica set as root with its module `database_mongodb_replica_set` (`library/`), the module `community.mongodb.mongodb_replicaset`
initiates without login, it relies on the localhost exception and cannot initiate a replica set with authorization.

```yaml
mongodb_config:
  replication:
    replSetName: 'rs0'
mongodb_secrets:
  - name: 'mongodb_keyfile'
    data: "{{ vault_mongodb_keyfile }}"
    target: 'MONGO_KEYFILE'
```

The keyfile has 6 to 1024 base64 characters, e.g. `openssl rand -base64 756`.

### Accounts

The role manages the accounts with `community.mongodb` as root over the address of the container after every start.
Accounts that are not listed are not changed.

```yaml
mongodb_accounts:
  - name: 'rocketchat'
    database: 'admin'
    roles:
      - { role: 'readWrite', db: 'rocketchat' }
      - { role: 'read', db: 'local' }
  - name: 'app'
    database: 'app'
    roles: [ 'readWrite' ]
mongodb_passwords:
  rocketchat: "{{ vault_mongodb_rocketchat_password }}"
  app: "{{ vault_mongodb_app_password }}"
```

`database` is the database of the account (`admin` by default), `roles` a list of role names of this database or dictionaries with `role` and `db`.
Every account needs a password in `mongodb_passwords`, the names of the accounts are unique.
MongoDB cannot compare passwords, the role checks the login of every account with its module `database_mongodb_logins` (`library/`)
and only sets the password of new accounts and of accounts that cannot log in, the passwords are options with `no_log` and never logged.
The host of the role needs `python3-pymongo`, the role installs it, the controller needs the collection `community.mongodb`.

### Secrets

`mongodb_secrets` is a list of podman secrets with `name`, `data` and `target`.

| Target | Mounted as | |
|---|---|---|
| `MONGO_INITDB_ROOT_PASSWORD` | `MONGO_INITDB_ROOT_PASSWORD_FILE` in `mongodb-init` | mandatory, used by the role to manage the replica set and the accounts |
| `MONGO_KEYFILE` | `security.keyFile` in mongod.conf, readable by `mongodb` only | mandatory for a replica set |

```yaml
mongodb_secrets:
  - name: 'mongodb_root_password'
    data: "{{ vault_mongodb_root_password }}"
    target: 'MONGO_INITDB_ROOT_PASSWORD'
```

The secrets are mounted to `/run/secrets/<name>`. The root password is only mounted into the container of the initialization,
the keyfile with mode 0400 for uid 999, mongod refuses a keyfile readable by others.
The image sets the root password only on the initialization, the role checks the login of root and stops if the password does not work,
the secret has to stay the password of the initialization.

### Allowed variables

The role only allows the options of `database_mongodb__config_allowed` in `mongodb_config`, the server parameters of `database_mongodb__parameters_allowed`
in `mongodb_config.setParameter`, the variables of the image in `database_mongodb__environment_allowed` and the secrets `MONGO_INITDB_ROOT_PASSWORD` and `MONGO_KEYFILE`,
it stops before any change if unknown options, parameters, variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or an option of another release, mongod does not start with unknown options.

The lists are generated for every release from the sources of MongoDB (7.0.48, 8.0.38, 8.3.17, 9.0.8) in `vars/options-<release>.yml`:

- options: the configs with the source `yaml` of the IDL files of the server and the log components of `systemLog.component`
- server parameters: the server parameters that can be set at startup, without the test only parameters

The image only reads `TZ` besides the variables of the initialization, `MONGO_INITDB_ROOT_USERNAME` and `MONGO_INITDB_DATABASE` are rejected,
the initialization is managed by the role.
The check uses the container after merging `mongodb_container`, so variables set with `mongodb_container.environment` are checked as well.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `mongodb_container`, it is merged over the default of the container.
The merge is not recursive, `mongodb_container.volumes` replaces the volumes of the databases and mongod.conf.
The role waits until MongoDB answers a `ping` in the container, shows the log of the service otherwise, and manages the replica set and the accounts afterwards.

### Validation

The role checks before any change:

- `mongodb_release` is supported and `mongodb_version` starts with it
- `mongodb_secrets` is a list of entries with `name`, `data` and `target` with unique names and targets, the secret `MONGO_INITDB_ROOT_PASSWORD` exists and is not empty
- neither a secret nor its file variable nor a variable of the initialization is set in `mongodb_environment`
- `mongodb_config` is a dictionary, its options and server parameters are known, not set by the role and no passwords, the values have no line breaks
- a replica set has the secret `MONGO_KEYFILE`
- `mongodb_accounts` is a list of entries with valid and unique names, valid databases and roles, root is not an account
- every account has a password in `mongodb_passwords`, `mongodb_passwords` has no passwords of unknown accounts and no empty passwords
- only allowed environment variables and secrets are set in the container

If `mongodb_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

MongoDB is restarted if it was running and a secret, the quadlet unit or mongod.conf changed, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `mongodb_autoupdate_enabled: true` and `mongodb_autoupdate_schedule`,
without `mongodb_autoupdate_schedule` the schedule of `container_update` is used.
A new release needs the matching `featureCompatibilityVersion` of the databases, MongoDB is upgraded one release at a time.

### Migration

- `mongodb_root_password` is replaced by the secret `MONGO_INITDB_ROOT_PASSWORD`, keep the former value, `mongodb_root_username` stays.
  The former role passed both as `type=env` secrets to the running container, the role does not use the podman secrets
  `mongodb_init_root_username` and `mongodb_init_root_password` anymore, remove them with `podman secret rm`.
- `mongodb_keyfile` is replaced by the secret `MONGO_KEYFILE`, the file `<mongodb_home>/etc/mongo-keyfile` is not used anymore.
  A replica set is configured with `mongodb_config.replication.replSetName` and initiated by the role, the pause asking to enable the replication is removed.
- The password of `mongodb_accounts` moves to `mongodb_passwords`, `database` and `roles` stay, `roles` is a list.
- `mongodb_version` is the tag of the image and has to start with `mongodb_release`, the former default `8.0` is the default release.
- `mongodb_flavor` and the image `mongodb/mongodb-community-server` are removed.
- `mongodb_publish` is replaced by `mongodb_container.publish`.
- The volumes `/etc/localtime` and `/etc/timezone` are removed, the timezone is set by podman.
- Without `mongod.conf` the former container started without `--config`, existing databases keep working, `security.authorization` replaces `--auth`.
- The service is not stopped on every run anymore, `podman___update_mode` is removed.
- The tag `database_mongodb` stays, the tag `database` is added.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-mongodb-default` | Only the mandatory variables and the root password, release 8.0 |
| `molecule-mongodb` | Release 9.0, IPv6, labels, another root user, options and a server parameter, a replica set with keyfile, accounts with roles |

`prepare` creates the podman network and pulls the image.
`side_effect` runs the role with `mongodb_container` not a dictionary, an unknown release, a secret without `target`, without the root password,
the root password and a variable of the initialization in the environment, an unknown option and server parameter, the option `net.port` set by the role,
a line break in a value, a replica set without keyfile, an account without password, the password of an unknown account
and an unknown environment variable in `mongodb_container.environment`
and checks that it fails with the expected message and the quadlet unit and mongod.conf are unchanged (tasks marked `expect ERROR`),
then it changes `operationProfiling.slowOpThresholdMs` on `molecule-mongodb`, mongod.conf changes, MongoDB has to restart and the initialization must not run again.
`verify` checks the quadlet unit without the variables of the initialization and with the keyfile as file, the service, the addresses and the environment of the container,
that `mongodb-init` is removed, mongod.conf without passwords, the version and the login of root, that a login is required, the primary of the replica set,
the server parameter, that `app` may write, `reader` may only read and that a wrong password is rejected,
it connects with the module `database_mongodb_test` of `molecule/default/library/` from the VM to the address of the container.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_mongodb
MOLECULE_TART_IMAGE='debian' molecule test
```
