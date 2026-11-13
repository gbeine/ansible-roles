mongo-express runs in the container image `c0d3.sh/container/mongo-express` (`latest` by default, `mongo_express_version` sets the tag) as podman quadlet.
The image is built with the `Dockerfile` of [mongo-express](https://github.com/mongo-express/mongo-express) and `ENABLE_OIDC=true`,
the web interface listens on port 8081. mongo-express keeps no data, the role creates no directories. MongoDB is not part of the role.

### Configuration

mongo-express is configured with environment variables in `mongo_express_environment`, merged over the default of the role.
The default sets `TZ` to `mongo_express_timezone` and `ME_CONFIG_AUTH_STRATEGY` to `form`.
The connection string and the passwords are passed with `mongo_express_secrets` (see Secrets).
Booleans may be given as YAML booleans, the role passes them as `true` or `false`.
The variables are described in the [README of mongo-express](https://github.com/mongo-express/mongo-express#readme), e.g.
`ME_CONFIG_MONGODB_ENABLE_ADMIN` (the image sets `true`) to show all databases, `ME_CONFIG_SITE_BASEURL` for a reverse proxy below a path
and `ME_CONFIG_OPTIONS_READONLY` or `ME_CONFIG_OPTIONS_NO_DELETE` to restrict the web interface.

```yaml
mongo_express_environment:
  ME_CONFIG_BASICAUTH_USERNAME: 'admin'
  ME_CONFIG_SITE_BASEURL: '/mongo/'
  ME_CONFIG_OPTIONS_NO_DELETE: true
```

### Authentication

Without login every visitor of mongo-express has full access to MongoDB, so the login is mandatory.
`ME_CONFIG_AUTH_STRATEGY` selects the way to log in, there is no way without login:

| Strategy | Login | Needs |
|---|---|---|
| `form` (default) | A login form, password managers can fill it | `ME_CONFIG_BASICAUTH_USERNAME` and the secret `ME_CONFIG_BASICAUTH_PASSWORD` |
| `basic` | HTTP basic authentication, the prompt of the browser | `ME_CONFIG_BASICAUTH_USERNAME` and the secret `ME_CONFIG_BASICAUTH_PASSWORD` |
| `oidc` | OpenID Connect | `ME_CONFIG_OIDCAUTH_ISSUER`, `ME_CONFIG_OIDCAUTH_CLIENTID` and the secret `ME_CONFIG_OIDCAUTH_SECRET` |

mongo-express only applies basic authentication with `ME_CONFIG_BASICAUTH_ENABLED=true` and OIDC with `ME_CONFIG_OIDCAUTH_ENABLED=true`,
the strategy alone does not protect it. The role sets both variables from `ME_CONFIG_AUTH_STRATEGY`, they must not be set in `mongo_express_environment`.
Without password mongo-express would accept `admin` and `pass`, the role never starts it without the secret.
The health check (`<ME_CONFIG_SITE_BASEURL>status`) is not behind the login.

### Secrets

`mongo_express_secrets` is a list of podman secrets with `name`, `data` and `target`, the usual name of the variable, e.g. `ME_CONFIG_MONGODB_URL`.
mongo-express reads the connection string and the passwords of the login from files,
the role mounts them to `/run/secrets/<name>` and sets the file variable, e.g. `ME_CONFIG_MONGODB_URL_FILE=/run/secrets/<name>`.
mongo-express has no file variable for the secrets of the sessions and the cookies and the password of the TLS key,
these are passed in the environment of the container with `type=env`, they are not part of the quadlet unit.

| Target | Passed as | Description |
|---|---|---|
| `ME_CONFIG_MONGODB_URL` | `ME_CONFIG_MONGODB_URL_FILE` | Connection string with the user and the password of MongoDB, mandatory |
| `ME_CONFIG_SITE_SESSIONSECRET` | environment | Signs the cookie of the session, mandatory |
| `ME_CONFIG_BASICAUTH_PASSWORD` | `ME_CONFIG_BASICAUTH_PASSWORD_FILE` | Password of the login with `form` and `basic` |
| `ME_CONFIG_OIDCAUTH_SECRET` | `ME_CONFIG_OIDCAUTH_SECRET_FILE` | Secret of the authorization code flow with `oidc` |
| `ME_CONFIG_OIDCAUTH_CLIENTSECRET` | `ME_CONFIG_OIDCAUTH_CLIENTSECRET_FILE` | Secret of the OIDC client |
| `ME_CONFIG_SITE_COOKIESECRET` | environment | Signs the cookies |
| `ME_CONFIG_MONGODB_TLS_CERT_KEY_FILE_PASSWORD` | environment | Password of the key of the TLS client certificate |

Neither a target nor its file variable may be set in `mongo_express_environment`.
The image sets `ME_CONFIG_MONGODB_URL=mongodb://mongo:27017` in its environment, mongo-express prefers the file of the secret.
The connection string of the root user of the official MongoDB image needs `authSource=admin`.

```yaml
mongo_express_secrets:
  - name: 'mongo_express_url'
    data: "mongodb://root:{{ vault_mongodb_root_password }}@mongodb:27017/?authSource=admin"
    target: 'ME_CONFIG_MONGODB_URL'
  - name: 'mongo_express_session'
    data: "{{ vault_mongo_express_session_secret }}"
    target: 'ME_CONFIG_SITE_SESSIONSECRET'
  - name: 'mongo_express_password'
    data: "{{ vault_mongo_express_password }}"
    target: 'ME_CONFIG_BASICAUTH_PASSWORD'
```

### Allowed variables

The role only allows the environment variables in `database_mongo_express__environment_allowed` and the secrets listed above,
it stops before any change if unknown variables or secrets are set.
This prevents unexpected behavior by accident, e.g. by a typo or a variable that has to be passed as secret.
The check uses the environment and the secrets of the container after merging `mongo_express_container`,
so variables set with `mongo_express_container.environment` are checked as well.

The list is generated from `config.default.js`, `app.js` and the `Dockerfile` of mongo-express 1.1.0-rc-4, new versions of the image may add variables.
It contains the `ME_CONFIG_*` variables without the secrets, `PORT`, `VCAP_APP_HOST`, `TZ`, the two variables set by the role and the file variables of the secrets.
Not allowed are `NODE_ENV` (`test` disables the protection against cross-site request forgery), `VCAP_SERVICES` (replaces the connection)
and the deprecated `ME_CONFIG_BASICAUTH`.

### Container

Ports, volumes, additional hosts (`etc_hosts`) and dependencies (`requires`) are changed with `mongo_express_container`, it is merged over the default of the container.
The merge is not recursive, `mongo_express_container.environment` replaces the environment including `mongo_express_environment`, use `mongo_express_environment` instead.
For a reverse proxy, e.g. Traefik, the labels are set with `mongo_express_labels`.
mongo-express connects to MongoDB only at the start, start it after MongoDB, e.g. with `requires`.

### Validation

The role checks before any change:

- `mongo_express_secrets` is a list of entries with `name`, `data` and `target` and unique names
- `ME_CONFIG_AUTH_STRATEGY` is `basic`, `form` or `oidc` and its variables and secrets are set
- the secrets `ME_CONFIG_MONGODB_URL` and `ME_CONFIG_SITE_SESSIONSECRET` are set
- neither a secret nor its file variable nor a variable set by the role is set in `mongo_express_environment`
- `ME_CONFIG_SITE_BASEURL` starts and ends with `/`
- booleans are `true` or `false`, values and the secrets passed in the environment contain no line breaks
- only allowed environment variables and secrets are set in the container

If `mongo_express_container` is no dictionary, merging it with the default fails before anything changes,
the same applies to a failing template in the variables, e.g. an unknown filter.

### Restart and updates

mongo-express is restarted if it was running and a secret or the quadlet unit changed, e.g. after changing `mongo_express_environment`, otherwise it is started and enabled.
Updates of the image are done by `container_update` with `mongo_express_autoupdate_enabled: true` and `mongo_express_autoupdate_schedule`,
without `mongo_express_autoupdate_schedule` the schedule of `container_update` is used.

### Migration

The role is new, there are no former variables.

### Tests

The molecule scenario `default` runs the role in two [tart](https://tart.run) VMs on a macOS controller, the base VM has to be Debian 13.
The playbooks creating and destroying the VMs live in `.molecule/tart/` in the repository root. The VMs need access to `c0d3.sh`.

| Platform | Test case |
|---|---|
| `molecule-mongo-express-default` | Only the mandatory variables, the login form, the connection string, the secret of the sessions and the password |
| `molecule-mongo-express` | IPv6, labels, basic authentication below `/mongo/`, `ME_CONFIG_OPTIONS_READONLY` and the secret of the cookies |

`prepare` installs curl, creates the podman network, pulls the images and starts MongoDB with a root user.
`side_effect` runs the role with `mongo_express_container` not a dictionary, a secret without `target`, without the connection string,
without the password, the password in the environment, the strategy `none`, `ME_CONFIG_BASICAUTH_ENABLED` in the environment,
a base URL without slash at the end, an invalid boolean, a line break in a value, `NODE_ENV` and the root password of MongoDB as secret
and checks that it fails with the expected message and the quadlet unit is unchanged (tasks marked `expect ERROR`),
then it changes `ME_CONFIG_DOCUMENTS_PER_PAGE` on `molecule-mongo-express`, the quadlet unit changes and mongo-express has to restart.
`verify` checks the quadlet unit with the mounted secrets and the secrets in the environment without their values,
the service, the addresses and the environment of the container with the variables set by the role,
the health check connected to MongoDB and the login: with basic authentication the start page answers 401 without and with a wrong password
and lists the databases with the password, with the login form curl logs in with a cookie file, a wrong password returns to the login form.

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd database_mongo_express
MOLECULE_TART_IMAGE='debian' molecule test
```
