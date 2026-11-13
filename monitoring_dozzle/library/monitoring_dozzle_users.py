#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: monitoring_dozzle_users
short_description: Writes the users of Dozzle with bcrypt hashes of their passwords
description:
  - Writes the file C(users.yml) of the provider simple of Dozzle with all given users, users missing in O(users) are removed.
  - Keeps the hash of a password if it matches the password, so the file only changes if a user or a password changes.
    New passwords are hashed with bcrypt and the cost of Dozzle (11).
  - The file is written as JSON, which is valid YAML and needs no YAML library.
  - Dozzle reads the file again if its modification time changes, it needs no restart.
requirements:
  - bcrypt
options:
  path:
    description: The file of the users, C(users.yml) in the data directory of Dozzle.
    type: path
    required: true
  users:
    description: The users without their passwords.
    type: list
    elements: dict
    required: true
    suboptions:
      username:
        description: The name to log in.
        type: str
        required: true
      name:
        description: The name shown by Dozzle.
        type: str
      email:
        description: The email, used for the avatar.
        type: str
      github:
        description: The login of the user at GitHub for the login with GitHub.
        type: str
      filter:
        description: The filter of the containers the user may see.
        type: str
      roles:
        description: The roles of the user, all roles if empty.
        type: list
        elements: str
  passwords:
    description: The passwords of the users by their usernames, users with GitHub may have none.
    type: dict
    required: true
  bcrypt_cost:
    description: The cost of new bcrypt hashes.
    type: int
    default: 11
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
- name: 'Write the users of Dozzle'
  monitoring_dozzle_users:
    path: '/opt/dozzle/data/users.yml'
    users:
      - username: 'admin'
        name: 'Admin'
        email: 'admin@example.org'
        roles: [ 'all' ]
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

import json
import os
import tempfile
import traceback

from ansible.module_utils.basic import AnsibleModule, missing_required_lib

BCRYPT_IMPORT_ERROR = None
try:
    import bcrypt
except ImportError:
    BCRYPT_IMPORT_ERROR = traceback.format_exc()


def read_users(path):
    """The users of an existing file, a file Dozzle or the role cannot read counts as empty."""
    try:
        with open(path, 'r') as handle:
            content = handle.read()
    except (IOError, OSError):
        return None, {}
    try:
        data = json.loads(content)
    except ValueError:
        return content, {}
    users = data.get('users') if isinstance(data, dict) else None
    return content, users if isinstance(users, dict) else {}


def password_matches(password, hashed):
    if not isinstance(hashed, str) or len(hashed) != 60:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except ValueError:
        return False


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type='path', required=True),
            users=dict(type='list', elements='dict', required=True, options=dict(
                username=dict(type='str', required=True),
                name=dict(type='str'),
                email=dict(type='str'),
                github=dict(type='str'),
                filter=dict(type='str'),
                roles=dict(type='list', elements='str'),
            )),
            passwords=dict(type='dict', required=True, no_log=True),
            bcrypt_cost=dict(type='int', default=11),
            owner=dict(type='str', default='root'),
            group=dict(type='str', default='root'),
            mode=dict(type='raw', default='0600'),
        ),
        supports_check_mode=True,
    )
    if BCRYPT_IMPORT_ERROR:
        module.fail_json(msg=missing_required_lib('bcrypt'), exception=BCRYPT_IMPORT_ERROR)

    params = module.params
    content, existing = read_users(params['path'])
    passwords = params['passwords'] or {}

    users = {}
    for user in params['users']:
        username = user['username']
        password = passwords.get(username)
        entry = dict(
            email=user.get('email') or '',
            name=user.get('name') or '',
            filter=user.get('filter') or '',
            roles=','.join(user.get('roles') or []),
        )
        if user.get('github'):
            entry['github'] = user['github']
        if password:
            former = existing.get(username) if isinstance(existing.get(username), dict) else {}
            hashed = former.get('password')
            if not password_matches(password, hashed):
                hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(params['bcrypt_cost'])).decode('utf-8')
            entry['password'] = hashed
        users[username] = entry

    new_content = json.dumps(dict(users=users), indent=2, sort_keys=True) + '\n'
    changed = new_content != content

    if changed and not module.check_mode:
        directory = os.path.dirname(params['path'])
        handle, temporary = tempfile.mkstemp(dir=directory, prefix='.users.', suffix='.tmp')
        try:
            with os.fdopen(handle, 'w') as output:
                output.write(new_content)
            module.atomic_move(temporary, params['path'])
        finally:
            if os.path.exists(temporary):
                os.remove(temporary)

    file_args = module.load_file_common_arguments(dict(path=params['path'], owner=params['owner'], group=params['group'], mode=params['mode']))
    if not module.check_mode or os.path.exists(params['path']):
        changed = module.set_fs_attributes_if_different(file_args, changed)

    module.exit_json(changed=changed, users=sorted(users))


if __name__ == '__main__':
    main()
