#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_n8n_owner_secret
short_description: Keeps the bcrypt hash of the password of the n8n owner in a podman secret
description:
  - n8n reads the owner from N8N_INSTANCE_OWNER_* on every start, the password as bcrypt hash.
  - The salt is derived from the password and the email, so the hash only changes with them and the service is not restarted on every run.
  - Compares the hash with the data of the existing podman secret and only replaces the secret if it differs, the hash is passed on stdin.
options:
  name:
    description: The name of the podman secret.
    type: str
    required: true
  email:
    description: The email of the owner, part of the salt.
    type: str
    required: true
  password:
    description: The password of the owner.
    type: str
    required: true
  rounds:
    description: The cost of bcrypt.
    type: int
    default: 10
requirements:
  - bcrypt (python3-bcrypt)
  - podman 4.7 or later (podman secret inspect --showsecret, podman secret create --replace)
'''

EXAMPLES = r'''
- name: 'Create the hash of the password of the owner'
  app_n8n_owner_secret:
    name: 'n8n_owner_password_hash'
    email: 'admin@example.org'
    password: 'Secret-Password-1'
'''

RETURN = r'''
name:
  description: The name of the podman secret.
  returned: always
  type: str
'''

import base64
import hashlib
import traceback

from ansible.module_utils.basic import AnsibleModule, missing_required_lib

try:
    import bcrypt
    BCRYPT_IMPORT_ERROR = None
except ImportError:
    BCRYPT_IMPORT_ERROR = traceback.format_exc()

STANDARD = b'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'
BCRYPT = b'./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'


def owner_hash(email, password, rounds):
    # 16 bytes of salt in the base64 alphabet of bcrypt, derived from email and password
    seed = hashlib.sha256(email.encode('utf-8') + b'\0' + password.encode('utf-8')).digest()[:16]
    salt = base64.b64encode(seed).rstrip(b'=').translate(bytes.maketrans(STANDARD, BCRYPT))
    return bcrypt.hashpw(password.encode('utf-8'), b'$2b$%02d$' % rounds + salt).decode('ascii')


def main():
    module = AnsibleModule(
        argument_spec=dict(
            name=dict(type='str', required=True),
            email=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            rounds=dict(type='int', default=10),
        ),
        supports_check_mode=True,
    )
    if BCRYPT_IMPORT_ERROR is not None:
        module.fail_json(msg=missing_required_lib('bcrypt'), exception=BCRYPT_IMPORT_ERROR)
    params = module.params
    wanted = owner_hash(params['email'], params['password'], params['rounds'])

    rc, out, err = module.run_command(['podman', 'secret', 'inspect', '--showsecret', '--format', '{{.SecretData}}', params['name']])
    if rc == 0 and out.strip() == wanted:
        module.exit_json(changed=False, name=params['name'])
    if not module.check_mode:
        rc, out, err = module.run_command(['podman', 'secret', 'create', '--replace', params['name'], '-'], data=wanted, binary_data=True)
        if rc != 0:
            module.fail_json(msg='podman secret create failed: %s' % (err.strip() or out.strip()))
    module.exit_json(changed=True, name=params['name'])


if __name__ == '__main__':
    main()
