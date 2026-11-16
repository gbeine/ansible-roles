#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: pki_easyrsa_cert_realm
short_description: Builds, rebuilds and renews the certificate of a realm with Easy-RSA
description:
  - Runs C(easyrsa build-server-full), C(build-client-full) or C(build-serverClient-full) with C(nopass) if the certificate does not exist.
  - If the type (extended key usage) or the subjectAltNames of the certificate differ, the certificate is revoked
    (C(revoke <name> superseded)), built again with a new key and the CRL is written (C(gen-crl)).
  - If the certificate expires within EASYRSA_PRE_EXPIRY_WINDOW days, it is renewed with C(easyrsa renew), the key stays.
    A certificate renewed before is revoked first (C(revoke-renewed <name> superseded)), Easy-RSA keeps only one renewed certificate.
  - The password of the CA is written to a temporary file with mode 0600 and passed as C(--passin=file:...),
    it is neither part of the environment nor of the command line.
  - In check mode the module only checks Easy-RSA, the CA, the password and the subjectAltNames and reports what it would do.
options:
  pki_dir:
    description: The directory of the PKI.
    type: path
    required: true
  easyrsa:
    description: The command of Easy-RSA.
    type: str
    default: easyrsa
  openssl:
    description: The command of OpenSSL, passed to Easy-RSA as EASYRSA_OPENSSL. Without it Easy-RSA uses its default.
    type: str
  name:
    description: The name of the realm, the commonName and the file name of the certificate.
    type: str
    required: true
  type:
    description: The type of the certificate, C(cs) is a combined client and server certificate.
    type: str
    choices: [ server, client, cs ]
    default: server
  san:
    description:
      - The subjectAltNames, C(DNS:<name>) or C(IP:<address>).
      - Without them a server certificate gets the commonName (C(--auto-san)), a client certificate none.
    type: list
    elements: str
    default: []
  password:
    description: The password of the private key of the CA.
    type: str
    required: true
  config:
    description: The options of Easy-RSA (EASYRSA_*), passed in the environment, null values are left out.
    type: dict
    default: {}
requirements:
  - Easy-RSA 3.2.3 or later
'''

EXAMPLES = r'''
- name: 'Create the certificate of a realm'
  pki_easyrsa_cert_realm:
    pki_dir: '/srv/secrets/pki'
    name: 'vpn.example.org'
    type: 'cs'
    san: [ 'DNS:vpn.example.org', 'IP:192.0.2.10' ]
    password: 'Secret-Password-1'
'''

RETURN = r'''
actions:
  description: The commands of Easy-RSA that were run, or would be run in check mode.
  returned: always
  type: list
  elements: str
crt:
  description: The certificate of the realm.
  returned: always
  type: str
'''

import ipaddress
import os
import re
import shutil
import tempfile

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text.converters import to_text

# renew is part of easyrsa again since 3.2.3, before it needed easyrsa-tools.lib
MIN_VERSION = (3, 2, 3)

COMMANDS = dict(server='build-server-full', client='build-client-full', cs='build-serverClient-full')
EKU_SERVER = 'TLS Web Server Authentication'
EKU_CLIENT = 'TLS Web Client Authentication'
EKUS = dict(server={EKU_SERVER}, client={EKU_CLIENT}, cs={EKU_SERVER, EKU_CLIENT})


class EasyRSA(object):
    def __init__(self, module):
        self.module = module
        params = module.params
        self.pki_dir = params['pki_dir']
        self.easyrsa = params['easyrsa']
        self.openssl = params['openssl'] or 'openssl'
        self.env = dict(EASYRSA_BATCH='1', EASYRSA_NO_VARS='1')
        if params['openssl']:
            self.env['EASYRSA_OPENSSL'] = params['openssl']
        for key, value in params['config'].items():
            if value is not None:
                self.env[key] = str(value)
        self.tmp_dir = None

    def password_files(self, password):
        # Two files, OpenSSL reads two lines of one file if -passin and -passout name the same file
        self.tmp_dir = tempfile.mkdtemp(prefix='pki_easyrsa_')
        files = []
        for name in ('passin', 'passout'):
            path = os.path.join(self.tmp_dir, name)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'w') as handle:
                handle.write(password + '\n')
            files.append(path)
        return files

    def cleanup(self):
        if self.tmp_dir:
            shutil.rmtree(self.tmp_dir, ignore_errors=True)
            self.tmp_dir = None

    def run(self, args, check=True):
        rc, out, err = self.module.run_command([self.easyrsa, '--batch', '--pki-dir=%s' % self.pki_dir] + args,
                                               environ_update=self.env)
        if check and rc != 0:
            self.module.fail_json(msg='easyrsa %s failed: %s' % (' '.join(a for a in args if not a.startswith('--pass')),
                                                                  (err.strip() or out.strip())))
        return rc, out, err

    def check_version(self):
        try:
            rc, out, err = self.module.run_command([self.easyrsa, '--version'], environ_update=self.env)
        except OSError as e:
            return 'Easy-RSA (%s) cannot be run: %s.' % (self.easyrsa, e)
        if rc != 0:
            return 'Easy-RSA (%s) cannot be run: %s.' % (self.easyrsa, err.strip() or out.strip() or 'not found')
        match = re.search(r'Version:\s*v?(\d+)\.(\d+)\.(\d+)', out)
        if not match:
            # Some packages do not set the version (Version: ~VER~)
            self.module.warn('The version of Easy-RSA (%s) cannot be read, the role needs Easy-RSA %s or later.'
                             % (self.easyrsa, '.'.join(str(v) for v in MIN_VERSION)))
            return None
        version = tuple(int(v) for v in match.groups())
        if version < MIN_VERSION:
            return 'Easy-RSA %s is too old, the role needs Easy-RSA %s or later.' % ('.'.join(match.groups()), '.'.join(str(v) for v in MIN_VERSION))
        return None

    def check_password(self, key, passin):
        rc, out, err = self.module.run_command([self.openssl, 'pkey', '-in', key, '-passin', 'file:%s' % passin, '-noout'])
        if rc != 0:
            return 'The password does not open the private key of the CA %s.' % key
        return None


def normalize_san(entry):
    # Returns (kind, value) comparable with the subjectAltNames printed by OpenSSL, or None if the entry is invalid
    kind, sep, value = entry.partition(':')
    if not sep or not value or re.search(r'[\s,]', value):
        return None
    if kind == 'DNS':
        return ('DNS', value.lower())
    if kind in ('IP', 'IP Address'):
        try:
            return ('IP', ipaddress.ip_address(to_text(value)).compressed)
        except ValueError:
            return None
    return None


def is_ip(name):
    try:
        ipaddress.ip_address(to_text(name))
        return True
    except ValueError:
        return False


def certificate_extensions(easyrsa, crt):
    # The extended key usage and the subjectAltNames of the certificate, read from the text of OpenSSL or LibreSSL
    rc, out, err = easyrsa.module.run_command([easyrsa.openssl, 'x509', '-in', crt, '-noout', '-text'])
    if rc != 0:
        easyrsa.module.fail_json(msg='The certificate %s cannot be read: %s' % (crt, err.strip() or out.strip()))
    lines = out.splitlines()
    eku = set()
    san = set()
    for index, line in enumerate(lines[:-1]):
        if 'X509v3 Extended Key Usage' in line:
            eku = set(item.strip() for item in lines[index + 1].split(',') if item.strip())
        if 'X509v3 Subject Alternative Name' in line:
            for item in lines[index + 1].split(','):
                normalized = normalize_san(item.strip())
                san.add(normalized if normalized else ('other', item.strip()))
    return eku, san


def main():
    module = AnsibleModule(
        argument_spec=dict(
            pki_dir=dict(type='path', required=True),
            easyrsa=dict(type='str', default='easyrsa'),
            openssl=dict(type='str'),
            name=dict(type='str', required=True),
            type=dict(type='str', choices=['server', 'client', 'cs'], default='server'),
            san=dict(type='list', elements='str', default=[]),
            password=dict(type='str', required=True, no_log=True),
            config=dict(type='dict', default={}),
        ),
        supports_check_mode=True,
    )
    params = module.params
    easyrsa = EasyRSA(module)
    pki_dir = easyrsa.pki_dir
    name = params['name']
    ca_crt = os.path.join(pki_dir, 'ca.crt')
    ca_key = os.path.join(pki_dir, 'private', 'ca.key')
    crt = os.path.join(pki_dir, 'issued', name + '.crt')
    key = os.path.join(pki_dir, 'private', name + '.key')
    req = os.path.join(pki_dir, 'reqs', name + '.req')
    renewed = os.path.join(pki_dir, 'renewed', 'issued', name + '.crt')
    result = dict(changed=False, actions=[], crt=crt)

    try:
        error = easyrsa.check_version()
        if error:
            module.fail_json(msg=error, **result)

        invalid = [entry for entry in params['san'] if normalize_san(entry) is None or entry.startswith('IP Address:')]
        if invalid:
            module.fail_json(msg='The subjectAltNames of %s are no DNS:<name> or IP:<address>: %s.' % (name, ', '.join(invalid)), **result)
        if params['san']:
            wanted_san = set(normalize_san(entry) for entry in params['san'])
            san_args = ['--san=%s' % entry for entry in params['san']]
        elif params['type'] in ('server', 'cs'):
            wanted_san = {('IP', ipaddress.ip_address(to_text(name)).compressed) if is_ip(name) else ('DNS', name.lower())}
            san_args = ['--auto-san']
        else:
            wanted_san = set()
            san_args = []
        wanted_eku = EKUS[params['type']]

        if not os.path.exists(ca_crt) or not os.path.exists(ca_key):
            module.fail_json(msg='The CA %s does not exist, run pki_easyrsa_ca first.' % ca_crt, **result)
        passin = easyrsa.password_files(params['password'])[0]
        error = easyrsa.check_password(ca_key, passin)
        if error:
            module.fail_json(msg=error, **result)

        actions = []
        if not os.path.exists(crt):
            leftovers = [path for path in (key, req) if os.path.exists(path)]
            if leftovers:
                module.fail_json(msg='The certificate %s does not exist, but %s. Easy-RSA does not overwrite them, '
                                     'remove them or restore the certificate.' % (crt, ' and '.join(leftovers)), **result)
            actions = ['build']
        else:
            eku, san = certificate_extensions(easyrsa, crt)
            if eku != wanted_eku or san != wanted_san:
                actions = ['revoke', 'build', 'gen-crl']
            else:
                window = int(params['config'].get('EASYRSA_PRE_EXPIRY_WINDOW') or 90)
                rc, out, err = module.run_command([easyrsa.openssl, 'x509', '-in', crt, '-noout', '-checkend', str(window * 86400)])
                if rc != 0:
                    actions = (['revoke-renewed', 'gen-crl'] if os.path.exists(renewed) else []) + ['renew']

        commands = {
            'build': san_args + [COMMANDS[params['type']], name, 'nopass'],
            'revoke': ['revoke', name, 'superseded'],
            'revoke-renewed': ['revoke-renewed', name, 'superseded'],
            'renew': ['renew', name],
            'gen-crl': ['gen-crl'],
        }
        result['actions'] = [' '.join(commands[action]) for action in actions]
        result['changed'] = len(actions) > 0
        if module.check_mode or not result['changed']:
            module.exit_json(**result)

        for action in actions:
            easyrsa.run(['--passin=file:%s' % passin] + commands[action])
        module.exit_json(**result)
    finally:
        easyrsa.cleanup()


if __name__ == '__main__':
    main()
