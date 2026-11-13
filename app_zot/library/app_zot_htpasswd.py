#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_zot_htpasswd
short_description: Writes the htpasswd file of zot with bcrypt hashes of the passwords
description:
  - Writes the htpasswd file of zot with all given users, users missing in O(passwords) are removed.
  - Keeps the hash of a password if it matches the password, so the file only changes if a user or a password changes.
    New passwords are hashed with bcrypt (C($2y$)) and the cost O(bcrypt_cost).
  - zot watches the file and reads it again when it changes, it needs no restart.
requirements:
  - bcrypt
options:
  path:
    description: The htpasswd file.
    type: path
    required: true
  passwords:
    description: The passwords of the users by their names, the names must not contain a colon.
    type: dict
    required: true
  bcrypt_cost:
    description: The cost of new bcrypt hashes.
    type: int
    default: 10
  owner:
    description: The owner of the file.
    type: str
    default: root
  group:
    description: The group of the file.
    type: str
    default: root
  mode:
    description: The mode of the file.
    type: raw
    default: '0600'
'''

EXAMPLES = r'''
- name: 'Write the users of zot'
  app_zot_htpasswd:
    path: '/opt/zot/etc/htpasswd'
    passwords:
      admin: 'secret-admin-password'
'''

RETURN = r'''
users:
  description: The names of the users in the file.
  returned: always
  type: list
  elements: str
'''

import os
import tempfile
import traceback

from ansible.module_utils.basic import AnsibleModule, missing_required_lib

BCRYPT_IMPORT_ERROR = None
try:
    import bcrypt
except ImportError:
    BCRYPT_IMPORT_ERROR = traceback.format_exc()


def read_hashes(path):
    """The content and the hashes by user of an existing file."""
    try:
        with open(path, 'r') as handle:
            content = handle.read()
    except (IOError, OSError):
        return None, {}
    hashes = {}
    for line in content.splitlines():
        name, separator, hashed = line.partition(':')
        if separator:
            hashes[name] = hashed
    return content, hashes


def password_matches(password, hashed):
    if not hashed or not hashed.startswith(('$2a$', '$2b$', '$2y$')):
        return False
    try:
        # The Python library knows $2b$, $2y$ is the same algorithm
        return bcrypt.checkpw(password.encode('utf-8'), ('$2b$' + hashed[4:]).encode('utf-8'))
    except ValueError:
        return False


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type='path', required=True),
            passwords=dict(type='dict', required=True, no_log=True),
            bcrypt_cost=dict(type='int', default=10),
            owner=dict(type='str', default='root'),
            group=dict(type='str', default='root'),
            mode=dict(type='raw', default='0600'),
        ),
        supports_check_mode=True,
    )
    if BCRYPT_IMPORT_ERROR:
        module.fail_json(msg=missing_required_lib('bcrypt'), exception=BCRYPT_IMPORT_ERROR)

    params = module.params
    content, existing = read_hashes(params['path'])

    lines = []
    for name in sorted(params['passwords']):
        if ':' in name or '\n' in name or not name:
            module.fail_json(msg='Invalid name of a user: %s' % name)
        password = str(params['passwords'][name])
        hashed = existing.get(name)
        if not password_matches(password, hashed):
            hashed = '$2y$' + bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(params['bcrypt_cost'])).decode('utf-8')[4:]
        lines.append('%s:%s' % (name, hashed))

    new_content = '\n'.join(lines) + '\n'
    changed = new_content != content

    if changed and not module.check_mode:
        handle, temporary = tempfile.mkstemp(dir=os.path.dirname(params['path']), prefix='.htpasswd.', suffix='.tmp')
        try:
            with os.fdopen(handle, 'w') as output:
                output.write(new_content)
            module.atomic_move(temporary, params['path'])
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    if not module.check_mode or os.path.exists(params['path']):
        file_args = module.load_file_common_arguments(dict(path=params['path'], owner=params['owner'], group=params['group'], mode=params['mode']))
        changed = module.set_fs_attributes_if_different(file_args, changed)

    module.exit_json(changed=changed, users=sorted(params['passwords']))


if __name__ == '__main__':
    main()
