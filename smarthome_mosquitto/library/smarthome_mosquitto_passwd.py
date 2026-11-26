#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: smarthome_mosquitto_passwd
short_description: Writes the password file of Mosquitto with hashes of the passwords
description:
  - Writes the password file of the plugin C(mosquitto_password_file) of Mosquitto with all given users,
    users missing in O(passwords) are removed.
  - New passwords are hashed like C(mosquitto_passwd) of Mosquitto 2.1 with C(sha512-pbkdf2),
    the line is C(<user>:$7$<iterations>$<salt>$<hash>) with a salt and a hash of 64 bytes in base64.
  - Keeps the hash of a password if it matches the password, so the file only changes if a user or a password changes.
    Hashes C($6$) (sha512) and C($7$) are checked, other hashes (e.g. argon2id) are replaced.
  - Needs no library, the hashes are computed with hashlib.
  - Mosquitto reads the file again on SIGHUP, it needs no restart.
options:
  path:
    description: The password file.
    type: path
    required: true
  passwords:
    description: The passwords by the names of the users.
    type: dict
    required: true
  iterations:
    description: The iterations of new hashes, the default of mosquitto_passwd 2.1.
    type: int
    default: 20000
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
- name: 'Write the passwords of Mosquitto'
  smarthome_mosquitto_passwd:
    path: '/opt/mosquitto/config/passwd'
    passwords:
      sensor: 'secret-sensor-password'
    owner: '1883'
    group: '1883'
'''

RETURN = r'''
users:
  description: The names of the users in the file.
  returned: always
  type: list
  elements: str
'''

import base64
import binascii
import hashlib
import hmac
import os
import tempfile

from ansible.module_utils.basic import AnsibleModule

# HASH_LEN of libcommon/password_common.c of Mosquitto 2.1, EVP_MAX_MD_SIZE
HASH_LEN = 64
# Mosquitto reads salts of 12 bytes (Mosquitto 1.x and 2.0) and of HASH_LEN bytes
SALT_LENGTHS = (12, HASH_LEN)


def read_hashes(path):
    """The content and the hashes of an existing file, lines without : are ignored."""
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


def decode(value):
    try:
        return base64.b64decode(value.encode('ascii'), validate=True)
    except (binascii.Error, ValueError, UnicodeEncodeError):
        return None


def password_matches(password, hashed):
    """Checks a hash $6$<salt>$<hash> or $7$<iterations>$<salt>$<hash> like pw__decode_* of Mosquitto."""
    if not isinstance(hashed, str):
        return False
    parts = hashed.split('$')
    if len(parts) == 4 and parts[0] == '' and parts[1] == '6':
        salt, expected = decode(parts[2]), decode(parts[3])
        if salt is None or expected is None or len(salt) not in SALT_LENGTHS or len(expected) != HASH_LEN:
            return False
        actual = hashlib.sha512(password.encode('utf-8') + salt).digest()
        return hmac.compare_digest(actual, expected)
    if len(parts) == 5 and parts[0] == '' and parts[1] == '7':
        try:
            iterations = int(parts[2])
        except ValueError:
            return False
        salt, expected = decode(parts[3]), decode(parts[4])
        if iterations < 1 or salt is None or expected is None or len(salt) not in SALT_LENGTHS or len(expected) != HASH_LEN:
            return False
        actual = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, iterations, HASH_LEN)
        return hmac.compare_digest(actual, expected)
    return False


def hash_password(password, iterations):
    """A new hash like pw__create_sha512_pbkdf2 and pw__encode_sha512_pbkdf2 of Mosquitto 2.1."""
    salt = os.urandom(HASH_LEN)
    hashed = hashlib.pbkdf2_hmac('sha512', password.encode('utf-8'), salt, iterations, HASH_LEN)
    return '$7$%d$%s$%s' % (iterations, base64.b64encode(salt).decode('ascii'), base64.b64encode(hashed).decode('ascii'))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            path=dict(type='path', required=True),
            passwords=dict(type='dict', required=True, no_log=True),
            iterations=dict(type='int', default=20000),
            owner=dict(type='str', default='root'),
            group=dict(type='str', default='root'),
            mode=dict(type='raw', default='0600'),
        ),
        supports_check_mode=True,
    )

    params = module.params
    if params['iterations'] < 1:
        module.fail_json(msg='iterations has to be at least 1.')
    passwords = params['passwords'] or {}
    invalid = sorted(str(name) for name, password in passwords.items()
                     if not isinstance(password, str) or password == '' or ':' in str(name)
                     or '\n' in str(name) or '\n' in password or '\r' in password)
    if invalid:
        module.fail_json(msg='The users need a password without line breaks and a name without colon: %s.' % ', '.join(invalid))

    content, existing = read_hashes(params['path'])

    lines = []
    for name in sorted(passwords):
        hashed = existing.get(name)
        if not password_matches(passwords[name], hashed):
            hashed = hash_password(passwords[name], params['iterations'])
        lines.append('%s:%s' % (name, hashed))

    new_content = ''.join(line + '\n' for line in lines)
    changed = new_content != content

    if changed and not module.check_mode:
        directory = os.path.dirname(params['path'])
        handle, temporary = tempfile.mkstemp(dir=directory, prefix='.passwd.', suffix='.tmp')
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

    module.exit_json(changed=changed, users=sorted(passwords))


if __name__ == '__main__':
    main()
