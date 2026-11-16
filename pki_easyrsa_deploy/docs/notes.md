The role copies the certificates of the realms created by `pki_easyrsa_cert` and the CA certificate of `pki_easyrsa_ca` from the controller to the host.
It is the only role of Easy-RSA working on the host, it creates no keys and needs no password.

```yaml
- hosts: 'all'
  roles:
    - 'pki_easyrsa_ca'
    - 'pki_easyrsa_cert'
    - 'pki_easyrsa_deploy'
```

### Realms

The role deploys the realms of `site_pki_realms` with `easyrsa: true` to `site_pki_realms_dir` of `common_globals` (default `/etc/pki/realms`).
The directories and owners of a realm are `common_globals__pki_realm_structure`, `owner` and `group` of a realm replace the owner and group
of all directories and files of the realm.

| Host | Content |
|---|---|
| `<realms_dir>/<name>/private/<name>.key` | private key, mode `0640`, group `ssl-cert` |
| `<realms_dir>/<name>/public/<name>.crt` | certificate, mode `0644` |
| `<realms_dir>/<name>/public/ca.crt` | CA certificate |
| `<realms_dir>/<name>/public/<name>.fullchain.crt` | certificate followed by the CA certificate |
| `<realms_dir>/<name>/cert.pem`, `fullchain.pem`, `chain.pem`, `privkey.pem` | links with the names of certbot |
| `<site_pki_ca_certificates_dir>/<CA name>.crt` | CA certificate, trusted by the host with `update-ca-certificates` |

The name of the CA certificate is `easyrsa_ca_cn` with all characters except letters, digits, `-` and `_` replaced by `_`.
The files are read from `easyrsa_pki_dir` on the controller (default `<site_pki_secrets_dir>/pki`).
`update-ca-certificates` only runs if the CA certificate changed.

### Validation

The role checks before any change:

- `easyrsa_ca_cn` is a string without line breaks
- `site_pki_realms` is a list of dictionaries with a name, `easyrsa` is a boolean
- the names of the realms with `easyrsa: true` consist of letters, digits, `_`, `.` and `-` and are unique
- `owner` and `group` of the realms are names of users and groups
- `ca.crt`, the keys and the certificates of the realms exist on the controller, otherwise `pki_easyrsa_ca` and `pki_easyrsa_cert` have to run first
- the users and groups exist on the host, the group `ssl-cert` is installed by `bootstrap_debian` with `debian_pki_enable`

### Migration

- The role does not depend on `pki_easyrsa_cert` anymore, the certificates are not created when the role runs.
  Plays run `pki_easyrsa_ca` and `pki_easyrsa_cert` before the role.
- The directory of the realms is `site_pki_realms_dir` of `common_globals`, the CA certificates are written to `site_pki_ca_certificates_dir`,
  `pki_easyrsa_ca_certificates_dir` is removed.
- The fullchain is written from the files on the controller, before it was created with `cat` on the host only if the certificate changed,
  a changed CA certificate did not change it.
- The directories are not created recursively anymore, the modes of files below them are not changed.
- The links of certbot replace existing files with the same name.
- The tasks run in check mode, they were skipped before.
- The tags are `pki` and `pki_easyrsa_deploy`.
- `app_gitlab_ce` reads the directory of the realms from `common_globals__pki_realms_dir`.

### Tests

The molecule scenario `default` runs `pki_easyrsa_ca` and `pki_easyrsa_cert` on the controller and the role in two [tart](https://tart.run) VMs
on a macOS controller, the base VM has to be Debian 13.
The base VM is cloned for every platform and the clones are deleted afterwards, the base VM itself is never changed.
The playbooks creating and destroying the VMs are shared by all tart scenarios and live in `.molecule/tart/` in the repository root.
Every platform has its own PKI in the ephemeral directory of molecule.

| Platform | Test case |
|---|---|
| `molecule-easyrsa-default` | The mandatory values only (`easyrsa_ca_cn`, `easyrsa_ca_password`), one realm with the default type `server` |
| `molecule-easyrsa` | CA with `EASYRSA_DN: org` and an EC key, EC certificates, a `cs` realm with DNS, IPv4 and IPv6 subjectAltNames, a `client` realm, a realm with `owner`, `group` and `easyrsa_config`, a realm of another role |

`prepare` installs `ca-certificates`, `openssl` and `ssl-cert` and creates the user and group `molecule`.
`side_effect` runs the roles with a wrong password, unknown options and `EASYRSA_PASSIN` in `easyrsa_ca_config`, invalid realms
(unknown type, invalid subjectAltName, `easyrsa_environment`, duplicate names, unknown keys, `easyrsa` no boolean), an invalid IP address,
`EASYRSA_CERT_EXPIRE` not greater than `EASYRSA_PRE_EXPIRY_WINDOW`, the role without the files of the PKI and with an unknown group
and checks that they fail with the expected messages before the files of the PKI and the certificates on the host change (tasks marked `expect ERROR`).
On `molecule-easyrsa` it adds a subjectAltName to `molecule-cs` (revoked, built again, CRL written) and renews `molecule-owned` twice
(renewed, then the renewed certificate revoked and renewed again).
`verify` checks the directories, files, modes, owners and links, the fullchains, the certificates against the CA certificates of the host,
the extended key usage and subjectAltNames, TLS handshakes with `openssl s_server` and `s_client` (with a client certificate for `molecule-cs`),
the encrypted private key of the CA and the revoked certificates in the database of the PKI.

Requirements on the controller: `tart`, `sshpass` (`brew install hudochenkov/sshpass/sshpass`), `molecule` and Easy-RSA 3.2.3 or later in `PATH` (`brew install easy-rsa`).

| Environment variable | Default | Description |
|---|---|---|
| `MOLECULE_TART_IMAGE` | `ghcr.io/cirruslabs/debian:latest` | Base VM or image that is cloned |
| `MOLECULE_TART_USER` | `admin` | SSH user of the base VM |
| `MOLECULE_TART_PASSWORD` | `admin` | Password of the SSH user, used to install the SSH key and for `sudo` |

```shell
cd pki_easyrsa_deploy
MOLECULE_TART_IMAGE='debian' molecule test
```
