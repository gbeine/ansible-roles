The job executor Joex of [Docspell](https://docspell.org) runs in the container image [docspell/joex](https://hub.docker.com/r/docspell/joex)
(`latest` by default, `docspell_joex_version` sets the tag, the image on Docker Hub is Docspell v0.42.0) as podman quadlet.
Joex processes the documents (text extraction, OCR, conversion, classification) and runs the periodic tasks, it listens on port 7878.
The entrypoint of the image starts the listener of `unoconv` and then Joex.
The REST server is installed by `app_docspell`, both connect to the same database, the database, e.g. PostgreSQL, is not part of the role.
Joex registers its `base-url` in the database, the REST server notifies Joex with it.

### Configuration

Joex reads the configuration file given as argument, the role writes `<docspell_joex_home>/joex.conf` and passes it as `/opt/joex.conf`.
A configuration file takes precedence over the environment variables `DOCSPELL_JOEX_*` of Docspell, they are not used.
`docspell_joex_config` is the content of the file as dictionary in the namespace `docspell.joex`, it is merged recursively over the default of the role,
`null` removes an option of the default.
The role writes every option as one line `docspell.joex.<path> = <value>`, the value is JSON, which is valid [HOCON](https://github.com/lightbend/config/blob/main/HOCON.md).

The role requires the database with `docspell.joex.jdbc.url` and `docspell.joex.jdbc.user`, the password of the database is a secret (see Secrets).

The default of the role sets `docspell.joex.base-url` to `http://<docspell_joex_ip>:7878`, the address the REST server reaches Joex with,
and `docspell.joex.bind.port` to `7878`. `docspell.joex.bind.address` is always `0.0.0.0`, the container has to listen on its address, the role stops if it is changed.
Every Joex needs its own `docspell.joex.app-id`, the default of Docspell is `joex1`.

```yaml
docspell_joex_config:
  docspell:
    joex:
      app-id: 'joex1'
      jdbc:
        url: 'jdbc:postgresql://10.89.0.20:5432/docspell'
        user: 'docspell'
      scheduler:
        pool-size: 2
```

The documents are stored in the database by default. The store `filesystem` uses the directory `/srv/docspell/files`, it is `<docspell_joex_home>/files` on the host.
The REST server needs the same directory, set the same home in `docspell_joex_home` and `docspell_home` then, the files of the configuration have different names.

`docspell_joex_environment` only takes `JAVA_OPTS` of the start script of the image, e.g. `-Xmx1536m`, and `TZ`, there is no default.
Without `docspell_joex_environment` the quadlet unit has no environment.
The time zone is set by podman with `docspell_joex_timezone` (`/etc/localtime` of the container), `TZ` is not needed.

### Secrets

The configuration of Docspell cannot read a value from a file, but HOCON includes files with `include required(file("…"))`.
`docspell_joex_secrets` is a list of entries with `name`, `data` and `target`, the target is the path of the option, e.g. `docspell.joex.jdbc.password`.
The role creates every entry as podman secret with the content `<target> = <data as JSON>`, mounts it as `/run/secrets/<name>.conf` with mode `0400`
and writes `include required(file("/run/secrets/<name>.conf"))` to the end of `joex.conf`.
The file needs the extension `.conf`, without an extension HOCON looks for `<name>.conf`, `<name>.json` and `<name>.properties`.
The passwords are neither part of `joex.conf`, the quadlet unit nor the environment of the container.
`data` may be a list as well, e.g. the passwords of encrypted PDF files in `docspell.joex.convert.decrypt-pdf.passwords`.

```yaml
docspell_joex_secrets:
  - name: 'docspell_joex_db_password'
    data: "{{ vault_docspell_db_password }}"
    target: 'docspell.joex.jdbc.password'
  - name: 'docspell_joex_pdf_passwords'
    data: "{{ vault_docspell_pdf_passwords }}"
    target: 'docspell.joex.convert.decrypt-pdf.passwords'
```

The password of the database (`docspell.joex.jdbc.password`) is required. Allowed targets are the options carrying passwords:
`docspell.joex.jdbc.password`, `docspell.joex.full-text-search.postgresql.jdbc.password`, `docspell.joex.files.stores.minio.secret-key`
and `docspell.joex.convert.decrypt-pdf.passwords`.
A target must not be set in `docspell_joex_config`. The names of the secrets are part of the paths.

### Allowed variables

The role only allows the options in `app_docspell_joex__config_allowed`, the secrets in `app_docspell_joex__secrets_allowed`
and the environment variables `JAVA_OPTS` and `TZ`, it stops before any change if unknown options, secrets or variables are set.
This prevents unexpected behavior by accident, e.g. by a typo, an option of the REST server or a password in the configuration file.
The options are generated from `modules/joex/src/main/resources/reference.conf` of Docspell v0.42.0, new versions may add options.
Lists, e.g. the arguments of the commands, and the dictionaries `docspell.joex.logging.levels` and `docspell.joex.full-text-search.postgresql.pg-config`,
whose keys are names of loggers or settings of PostgreSQL, are checked as one option, their content is not checked.
The check of the environment uses the environment of the container after merging `docspell_joex_container`.

### Container

The container is named `docspell-joex`. Ports, volumes, additional hosts (`etc_hosts`) and the dependencies are changed with `docspell_joex_container`,
it is merged over the default of the container.
The dependencies of the quadlet unit are lists: `requires`, `wants`, `after`, `part_of` and `binds_to` are units,
`requires_mounts_for` are paths. They are written to `[Unit]` as `Requires=`, `Wants=`, `After=`, `PartOf=`, `BindsTo=` and `RequiresMountsFor=`.

```yaml
docspell_joex_container:
  requires: [ 'postgres.service' ]
  after: [ 'postgres.service' ]
```

The merge is not recursive, `volumes` replaces the configuration file and the directory of the files, `environment` replaces `docspell_joex_environment`.
Labels are set with `docspell_joex_labels`.

### Validation

The role checks before any change:

- `docspell_joex_secrets` is a list of entries with `name`, `data` and `target`, the names are unique and valid
- the required options are set and not empty
- only known options are set in `docspell_joex_config`, no secret and no changed `docspell.joex.bind.address`, the values contain no line breaks
- the password of the database is a secret, only allowed targets are used
- only allowed environment variables are set in the container, the values contain no line breaks

If `docspell_joex_config` or `docspell_joex_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Check mode

The role runs with `--check` without failing, also on a host where it never ran before.
It reports the changes of `joex.conf`, the secrets and the quadlet unit, the service is neither started nor restarted.

### Restart and updates

Joex is restarted if it was running and a secret, `joex.conf` or the quadlet unit changed, otherwise it is started and enabled.
If the start fails, the role stops with the last lines of the journal of the service.
Updates of the image are done by `container_update` with `docspell_joex_autoupdate_enabled: true` and `docspell_joex_autoupdate_schedule`,
without `docspell_joex_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

Joex was part of `app_docspell`, the role `app_docspell_joex` installs it now.

- The container was named `joex`, it is `docspell-joex` now. Stop the former service and remove its quadlet unit before the first run:
  `systemctl stop joex` and `rm /etc/containers/systemd/joex.container`, then `systemctl daemon-reload`.
- `docspell_joex_ip`, `docspell_joex_ipv6`, `docspell_joex_hostname` and `docspell_joex_container` keep their names,
  `docspell_joex_home`, `docspell_joex_network`, `docspell_joex_timezone` and `docspell_joex_config` are new and mandatory.
- The options of `docspell.joex` move from `docspell_config` to `docspell_joex_config`, the file is `joex.conf` instead of the shared `docspell.conf`.
- The passwords move to `docspell_joex_secrets`, e.g. `docspell.joex.jdbc.password`.
- `docspell.joex.bind.address` is `0.0.0.0`, `docspell.joex.base-url` is `http://<docspell_joex_ip>:7878` by default.
- `TZ` is no longer set in the environment and `/etc/localtime` and `/etc/timezone` of the host are no longer mounted,
  the time zone is set by podman with `docspell_joex_timezone`.
- The directory of the files is mounted with `z` instead of `Z`, so both containers can use it.
- `podman___update_mode` and the handler are gone, the role neither stops the container nor pulls the image or recreates the container.
- The tags are `app` and `app_docspell_joex`, the former tag `app_docspell` does not run Joex anymore.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root.

| Platform | Test case |
|---|---|
| `molecule-docspell-joex-default` | Only the mandatory variables: the database and the secret of its password |
| `molecule-docspell-joex` | IPv6, labels, dependencies, `JAVA_OPTS`, own options and the passwords of PDF files as a list in a second secret |

`prepare` creates the podman network, pulls the images and starts PostgreSQL 17 with a password, Joex creates the schema of the database itself.
`check` runs `converge` with `--check` on the new VMs.
`side_effect` runs the role with `docspell_joex_container` and `docspell_joex_config` not a dictionary, a secret without target,
without the password of the database, with an unknown secret, the password in the configuration, an unknown option, a changed `bind.address`,
without `jdbc.url`, a line break in an option and in the environment and an unknown environment variable
and checks that it fails with the expected message and `joex.conf` and the quadlet unit are unchanged (tasks marked `expect ERROR`),
then it adds a password of PDF files on `molecule-docspell-joex`, Joex has to restart, `molecule-docspell-joex-default` runs again without a change and must not restart.
`verify` checks `joex.conf` with the includes and without the passwords, the quadlet unit with the secrets, the dependencies and without `TZ`,
the service without automatic restarts, the addresses, the environment and the time zone, the version of the API
and that Joex registered its `base-url` in the table `node` of PostgreSQL.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd app_docspell_joex
MOLECULE_TART_IMAGE='debian' molecule test
```
