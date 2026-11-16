#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: pki_easyrsa_ca_pki
short_description: Initializes a PKI of Easy-RSA and builds its CA
description:
  - Runs C(easyrsa init-pki) if the directory of the PKI does not exist or is empty and C(easyrsa build-ca) if C(ca.crt) does not exist.
  - An existing CA is never replaced, an existing C(private/ca.key) has to be opened by the password.
  - Runs C(easyrsa gen-crl) if C(crl.pem) does not exist or its nextUpdate is less than half of C(EASYRSA_CRL_DAYS) away,
    so the CRL never expires if the module runs at least every C(EASYRSA_CRL_DAYS / 2) days.
  - The password is written to temporary files with mode 0600 and passed as C(--passin=file:...) and C(--passout=file:...),
    it is neither part of the environment nor of the command line.
  - In check mode the module only checks Easy-RSA, the PKI and the password and reports what it would do.
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
  cn:
    description: The commonName of the CA.
    type: str
    required: true
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
- name: 'Create the PKI and the CA'
  pki_easyrsa_ca_pki:
    pki_dir: '/srv/secrets/pki'
    cn: 'Example CA'
    password: 'Secret-Password-1'
    config:
      EASYRSA_ALGO: 'ec'
      EASYRSA_CURVE: 'secp384r1'
      EASYRSA_CRL_DAYS: 180
'''

RETURN = r'''
actions:
  description: The commands of Easy-RSA that were run, or would be run in check mode.
  returned: always
  type: list
  elements: str
ca_crt:
  description: The certificate of the CA.
  returned: always
  type: str
crl:
  description: The CRL of the CA.
  returned: always
  type: str
'''

import calendar
import os
import re
import shutil
import tempfile
import time

from ansible.module_utils.basic import AnsibleModule

# renew is part of easyrsa again since 3.2.3, before it needed easyrsa-tools.lib
MIN_VERSION = (3, 2, 3)

# The default of EASYRSA_CRL_DAYS of Easy-RSA
CRL_DAYS = 180
# nextUpdate=Dec  6 10:00:00 2026 GMT of OpenSSL and LibreSSL, the months are not localized
MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
NEXT_UPDATE = re.compile(r'nextUpdate=(\w{3})\s+(\d{1,2})\s+(\d{2}):(\d{2}):(\d{2})\s+(\d{4})\s+GMT')


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

    def crl_expires(self, crl, days):
        """True if the CRL does not exist or its nextUpdate is less than half of days away"""
        if not os.path.exists(crl):
            return True
        rc, out, err = self.module.run_command([self.openssl, 'crl', '-in', crl, '-noout', '-nextupdate'])
        match = NEXT_UPDATE.search(out)
        if rc != 0 or not match or match.group(1) not in MONTHS:
            self.module.fail_json(msg='The nextUpdate of the CRL %s cannot be read: %s' % (crl, err.strip() or out.strip()))
        month, day, hour, minute, second, year = match.groups()
        next_update = calendar.timegm((int(year), MONTHS.index(month) + 1, int(day), int(hour), int(minute), int(second), 0, 0, 0))
        return next_update - time.time() < days * 86400 / 2

    def check_password(self, key, passin):
        rc, out, err = self.module.run_command([self.openssl, 'pkey', '-in', key, '-passin', 'file:%s' % passin, '-noout'])
        if rc != 0:
            return 'The password does not open the private key of the CA %s.' % key
        return None


def main():
    module = AnsibleModule(
        argument_spec=dict(
            pki_dir=dict(type='path', required=True),
            easyrsa=dict(type='str', default='easyrsa'),
            openssl=dict(type='str'),
            cn=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            config=dict(type='dict', default={}),
        ),
        supports_check_mode=True,
    )
    easyrsa = EasyRSA(module)
    pki_dir = easyrsa.pki_dir
    ca_crt = os.path.join(pki_dir, 'ca.crt')
    ca_key = os.path.join(pki_dir, 'private', 'ca.key')
    crl = os.path.join(pki_dir, 'crl.pem')
    crl_days = int(easyrsa.env.get('EASYRSA_CRL_DAYS', CRL_DAYS))
    result = dict(changed=False, actions=[], ca_crt=ca_crt, crl=crl)

    try:
        error = easyrsa.check_version()
        if error:
            module.fail_json(msg=error, **result)
        passin, passout = easyrsa.password_files(module.params['password'])

        initialized = os.path.isdir(os.path.join(pki_dir, 'private'))
        if not initialized and os.path.isdir(pki_dir) and os.listdir(pki_dir):
            module.fail_json(msg='%s is no PKI of Easy-RSA and not empty, the role does not initialize it.' % pki_dir, **result)
        if os.path.exists(ca_crt) and not os.path.exists(ca_key):
            module.fail_json(msg='The CA %s has no private key %s.' % (ca_crt, ca_key), **result)
        if os.path.exists(ca_key):
            error = easyrsa.check_password(ca_key, passin)
            if error:
                module.fail_json(msg=error, **result)

        if not initialized:
            result['actions'].append('init-pki')
        if not os.path.exists(ca_crt):
            result['actions'].append('build-ca')
        if not os.path.exists(ca_crt) or easyrsa.crl_expires(crl, crl_days):
            result['actions'].append('gen-crl')
        result['changed'] = len(result['actions']) > 0
        if module.check_mode or not result['changed']:
            module.exit_json(**result)

        if not initialized:
            easyrsa.run(['init-pki'])
            os.chmod(pki_dir, 0o700)
        if not os.path.exists(ca_crt):
            easyrsa.run(['--req-cn=%s' % module.params['cn'], '--passin=file:%s' % passin, '--passout=file:%s' % passout, 'build-ca'])
        if 'gen-crl' in result['actions']:
            easyrsa.run(['--passin=file:%s' % passin, 'gen-crl'])
        module.exit_json(**result)
    finally:
        easyrsa.cleanup()


if __name__ == '__main__':
    main()
