#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_nodered_users
short_description: Creates the users of adminAuth of Node-RED with bcrypt hashes of their passwords
description:
  - Node-RED reads the users of the editor from adminAuth in settings.js, the passwords as bcrypt hashes.
  - The salt is derived from the name and the password, so the hash only changes with them,
    settings.js stays the same and Node-RED is not restarted on every run.
  - The module only computes the users, it changes nothing and never reports changed.
options:
  users:
    description: The users with name and permissions (* or read, defaults to *).
    type: list
    elements: dict
    required: true
  passwords:
    description: The passwords of the users by name.
    type: dict
    required: true
  rounds:
    description: The cost of bcrypt.
    type: int
    default: 10
requirements:
  - bcrypt (python3-bcrypt)
'''

EXAMPLES = r'''
- name: 'Create the users of adminAuth'
  app_nodered_users:
    users:
      - name: 'admin'
      - name: 'viewer'
        permissions: 'read'
    passwords:
      admin: 'secret-admin-password'
      viewer: 'secret-viewer-password'
  register: 'users'
'''

RETURN = r'''
users:
  description: The users for adminAuth with username, password (the bcrypt hash) and permissions.
  returned: always
  type: list
  elements: dict
  sample: [ { "username": "admin", "password": "$2b$10$...", "permissions": "*" } ]
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


def password_hash(name, password, rounds):
    # 16 bytes of salt in the base64 alphabet of bcrypt, derived from name and password
    seed = hashlib.sha256(name.encode('utf-8') + b'\0' + password.encode('utf-8')).digest()[:16]
    salt = base64.b64encode(seed).rstrip(b'=').translate(bytes.maketrans(STANDARD, BCRYPT))
    return bcrypt.hashpw(password.encode('utf-8'), b'$2b$%02d$' % rounds + salt).decode('ascii')


def main():
    module = AnsibleModule(
        argument_spec=dict(
            users=dict(type='list', elements='dict', required=True),
            passwords=dict(type='dict', required=True, no_log=True),
            rounds=dict(type='int', default=10),
        ),
        supports_check_mode=True,
    )
    if BCRYPT_IMPORT_ERROR is not None:
        module.fail_json(msg=missing_required_lib('bcrypt'), exception=BCRYPT_IMPORT_ERROR)
    params = module.params

    users = []
    for user in params['users']:
        name = str(user.get('name', ''))
        if name not in params['passwords']:
            module.fail_json(msg='The user %s has no password.' % name)
        users.append(dict(
            username=name,
            password=password_hash(name, str(params['passwords'][name]), params['rounds']),
            permissions=str(user.get('permissions') or '*'),
        ))
    module.exit_json(changed=False, users=users)


if __name__ == '__main__':
    main()
