The REST server of [Docspell](https://docspell.org) runs in the container image [docspell/restserver](https://hub.docker.com/r/docspell/restserver)
(`latest` by default, `docspell_version` sets the tag, the image on Docker Hub is Docspell v0.42.0) as podman quadlet.
It serves the web interface and the API on port 7880. The job executor Joex runs in its own container and is installed by `app_docspell_joex`,
both connect to the same database, the REST server notifies Joex with the address Joex registers in the database.
The database, e.g. PostgreSQL, is not part of the role.

### Configuration

The REST server reads the configuration file given as argument, the role writes `<docspell_home>/docspell.conf` and passes it as `/opt/docspell.conf`.
A configuration file takes precedence over the environment variables `DOCSPELL_SERVER_*` of Docspell, they are not used.
`docspell_config` is the content of the file as dictionary in the namespace `docspell.server`, it is merged recursively over the default of the role,
`null` removes an option of the default.
The role writes every option as one line `docspell.server.<path> = <value>`, the value is JSON, which is valid [HOCON](https://github.com/lightbend/config/blob/main/HOCON.md).

The role requires `docspell.server.base-url`, the public URL of Docspell, and the database with `docspell.server.backend.jdbc.url` and `docspell.server.backend.jdbc.user`,
the password of the database is a secret (see Secrets). The default of `docspell.server.backend.jdbc` of Docspell is a H2 database in `/tmp` of the container, it is lost at every restart.

The default of the role sets `docspell.server.internal-url` to `http://<docspell_ip>:7880` and `docspell.server.bind.port` to `7880`.
`docspell.server.bind.address` is always `0.0.0.0`, the container has to listen on its address, the role stops if it is changed.

```yaml
docspell_config:
  docspell:
    server:
      base-url: 'https://docspell.example.org'
      app-id: 'rest1'
      backend:
        jdbc:
          url: 'jdbc:postgresql://10.89.0.20:5432/docspell'
          user: 'docspell'
        signup:
          mode: 'closed'
      logging:
        levels:
          docspell: 'Info'
```

The documents are stored in the database by default. The store `filesystem` uses the directory `/srv/docspell/files`, it is `<docspell_home>/files` on the host.
Joex needs the same directory, set the same home in `docspell_joex_home` and `docspell_home` then.

`docspell_environment` only takes `JAVA_OPTS` of the start script of the image, e.g. `-Xmx512m`, and `TZ`, there is no default.
Without `docspell_environment` the quadlet unit has no environment.
The time zone is set by podman with `docspell_timezone` (`/etc/localtime` of the container), `TZ` is not needed.

### Secrets

The configuration of Docspell cannot read a value from a file, but HOCON includes files with `include required(file("…"))`.
`docspell_secrets` is a list of entries with `name`, `data` and `target`, the target is the path of the option, e.g. `docspell.server.backend.jdbc.password`.
The role creates every entry as podman secret with the content `<target> = <data as JSON>`, mounts it as `/run/secrets/<name>.conf` with mode `0400`
and writes `include required(file("/run/secrets/<name>.conf"))` to the end of `docspell.conf`.
The file needs the extension `.conf`, without an extension HOCON looks for `<name>.conf`, `<name>.json` and `<name>.properties`.
The passwords are neither part of `docspell.conf`, the quadlet unit nor the environment of the container.
`data` may be a list or a dictionary as well, e.g. the providers of `docspell.server.openid` with their `client-secret`.

```yaml
docspell_secrets:
  - name: 'docspell_db_password'
    data: "{{ vault_docspell_db_password }}"
    target: 'docspell.server.backend.jdbc.password'
  - name: 'docspell_server_secret'
    data: "{{ vault_docspell_server_secret }}"
    target: 'docspell.server.auth.server-secret'
```

The password of the database (`docspell.server.backend.jdbc.password`) is required. Allowed targets are the options carrying passwords:
`docspell.server.auth.server-secret`, `docspell.server.openid`, `docspell.server.integration-endpoint.http-basic.password`,
`docspell.server.integration-endpoint.http-header.header-value`, `docspell.server.admin-endpoint.secret`,
`docspell.server.full-text-search.postgresql.jdbc.password`, `docspell.server.backend.jdbc.password`,
`docspell.server.backend.signup.new-invite-password` and `docspell.server.backend.files.stores.minio.secret-key`.
A target must not be set in `docspell_config`. The names of the secrets are part of the paths, they consist of letters, digits, `_`, `.` and `-`.

Without `docspell.server.auth.server-secret` Docspell creates a random secret at every start and the sessions end with every restart.

### Allowed variables

The role only allows the options in `app_docspell__config_allowed`, the secrets in `app_docspell__secrets_allowed`
and the environment variables `JAVA_OPTS` and `TZ`, it stops before any change if unknown options, secrets or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo, an option of Joex or a password in the configuration file.
The options are generated from `modules/restserver/src/main/resources/reference.conf` of Docspell v0.42.0, new versions may add options.
Lists, e.g. `docspell.server.openid`, and the dictionaries `docspell.server.logging.levels` and `docspell.server.full-text-search.postgresql.pg-config`,
whose keys are names of loggers or settings of PostgreSQL, are checked as one option, their content is not checked.
The check of the environment uses the environment of the container after merging `docspell_container`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `docspell_container`, it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

```yaml
docspell_container:
  requires: [ 'postgres.service' ]
  after: [ 'postgres.service' ]
```

The merge is not recursive, `volumes` replaces the configuration file and the directory of the files, `environment` replaces `docspell_environment`.
For a reverse proxy, e.g. Traefik, the labels are set with `docspell_labels`.

### Validation

The role checks before any change:

- `docspell_secrets` is a list of entries with `name`, `data` and `target`, the names are unique and valid
- the required options are set and not empty
- only known options are set in `docspell_config`, no secret and no changed `docspell.server.bind.address`, the values contain no line breaks
- the password of the database is a secret, only allowed targets are used
- only allowed environment variables are set in the container, the values contain no line breaks

If `docspell_config` or `docspell_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of `docspell.conf`, the secrets and the quadlet unit, the service is neither started nor restarted.

### Restart and updates

The REST server is restarted if it was running and a secret, `docspell.conf` or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `docspell_autoupdate_enabled: true` and `docspell_autoupdate_schedule`,
without `docspell_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The former role installed the REST server and Joex together, Joex is installed by `app_docspell_joex` now.

- `docspell_config` contained both namespaces, it only takes `docspell.server` now, the options of `docspell.joex` move to `docspell_joex_config`.
- The passwords move from `docspell_config` to `docspell_secrets`, e.g. `docspell.server.backend.jdbc.password`.
- `docspell_joex_ip`, `docspell_joex_ipv6`, `docspell_joex_hostname` and `docspell_joex_container` are variables of `app_docspell_joex`.
- The configuration file was written without `bind.address`, it is `0.0.0.0` now, `internal-url` is `http://<docspell_ip>:7880` by default.
- `TZ` is no longer set in the environment and `/etc/localtime` and `/etc/timezone` of the host are no longer mounted,
  the time zone is set by podman with `docspell_timezone`.
- The directory of the files is mounted with `z` instead of `Z`, so both containers can use it.
- `docspell_labels` has no default anymore, without it the container has no labels.
- `podman___update_mode` and the handler `Restart docspell container` are gone, the role neither stops the container nor pulls the image or recreates the container.
- The tag `app` is added to `app_docspell`.
- `docspell_environment`, `docspell_secrets`, `docspell_autoupdate_schedule` and the dependencies in `docspell_container` are new.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-docspell-default` | Only the mandatory variables: the base URL, the database and the secret of its password |
| `molecule-docspell` | IPv6, labels, dependencies, `JAVA_OPTS`, own options including `logging.levels` and the server secret as a second secret |

`prepare` creates the podman network, pulls the images and starts PostgreSQL 17 with a password.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `docspell_container` and `docspell_config` not a dictionary, a secret without target, an invalid name of a secret,
without the password of the database, with an unknown secret, the password in the configuration, an unknown option, a changed `bind.address`,
without `base-url`, a line break in an option and in the environment and an unknown environment variable
and checks that it fails with the expected message and `docspell.conf` and the quadlet unit are unchanged (tasks marked `expect ERROR`),
then it changes the server secret on `molecule-docspell`, Docspell has to restart, `molecule-docspell-default` runs again without a change and must not restart.
`verify` checks `docspell.conf` with the includes and without the passwords, the quadlet unit with the secrets, the dependencies and without `TZ`,
the service without automatic restarts, the addresses, the environment and the time zone, registers an account and logs in with it.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_docspell
MOLECULE_TART_IMAGE='debian' molecule test
```
