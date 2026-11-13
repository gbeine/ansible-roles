#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_karakeep_admin
short_description: Creates the administrator of Karakeep and keeps its name and password up to date
description:
  - Runs node in the container of Karakeep with better-sqlite3 and bcryptjs of the image and changes the database C(/data/db.db)
    in one transaction. The name, the email and the password are passed on stdin, they are never arguments of a process.
  - Looks up the user by its email and creates it as administrator with a confirmed email and a password account
    if it does not exist, so the first user who signs up does not become the administrator.
  - Checks the password with bcrypt and only sets it if it differs, keeps the name up to date
    and makes the user an administrator with a confirmed email.
options:
  container:
    description: The name of the container of Karakeep.
    type: str
    required: true
  name:
    description: The name of the administrator.
    type: str
    required: true
  email:
    description: The email address of the administrator, Karakeep identifies users by it.
    type: str
    required: true
  password:
    description: The password of the administrator.
    type: str
    required: true
  database:
    description: The database of Karakeep in the container, C(DATA_DIR)/db.db.
    type: str
    default: /data/db.db
'''

EXAMPLES = r'''
- name: 'Create the administrator'
  app_karakeep_admin:
    container: 'karakeep'
    name: 'Admin'
    email: 'admin@example.org'
    password: 'secret-admin-password'
'''

RETURN = r'''
created:
  description: Whether the administrator was created.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

WORKDIR = '/app/apps/workers'

# Reads {name, email, password, database} from stdin, writes the result as the last line of stdout
SCRIPT = r'''
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { createRequire } = require('module');

// bcryptjs is a dependency of @karakeep/trpc, the isolated node_modules of the workers only link the direct dependencies
function loadBcrypt() {
    try {
        return require('bcryptjs');
    } catch (error) {
        const trpc = fs.realpathSync(path.join(process.cwd(), 'node_modules', '@karakeep', 'trpc'));
        return createRequire(path.join(trpc, 'package.json'))('bcryptjs');
    }
}

// Passwords set before better-auth are stored as bcrypt-salted:<salt>:<hash> of password + salt
function passwordMatches(bcrypt, hash, password) {
    if (!hash) return false;
    if (!hash.startsWith('bcrypt-salted:')) return bcrypt.compareSync(password, hash);
    const rest = hash.slice('bcrypt-salted:'.length);
    const separator = rest.indexOf(':');
    if (separator === -1) return false;
    return bcrypt.compareSync(password + rest.slice(0, separator), rest.slice(separator + 1));
}

function run(data) {
    const Database = require('better-sqlite3');
    const bcrypt = loadBcrypt();
    const db = new Database(data.database, { fileMustExist: true });
    try {
        db.pragma('busy_timeout = 10000');
        const email = data.email.toLowerCase();
        const now = Date.now();
        return db.transaction(() => {
            let user = db.prepare('SELECT id, name, role, emailVerified FROM user WHERE email = ?').get(email);
            if (!user) {
                const id = crypto.randomUUID();
                db.prepare('INSERT INTO user (id, name, email, emailVerified, role, createdAt, updatedAt) VALUES (?, ?, ?, 1, ?, ?, ?)')
                    .run(id, data.name, email, 'admin', now, now);
                db.prepare('INSERT INTO account (id, accountId, providerId, userId, password, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?, ?)')
                    .run(crypto.randomUUID(), id, 'credential', id, bcrypt.hashSync(data.password, 10), now, now);
                return { changed: true, created: true };
            }
            let changed = false;
            if (user.name !== data.name || user.role !== 'admin' || !user.emailVerified) {
                db.prepare('UPDATE user SET name = ?, role = ?, emailVerified = 1, updatedAt = ? WHERE id = ?').run(data.name, 'admin', now, user.id);
                changed = true;
            }
            const account = db.prepare('SELECT id, password FROM account WHERE userId = ? AND providerId = ?').get(user.id, 'credential');
            if (!account) {
                db.prepare('INSERT INTO account (id, accountId, providerId, userId, password, createdAt, updatedAt) VALUES (?, ?, ?, ?, ?, ?, ?)')
                    .run(crypto.randomUUID(), user.id, 'credential', user.id, bcrypt.hashSync(data.password, 10), now, now);
                changed = true;
            } else if (!passwordMatches(bcrypt, account.password, data.password)) {
                db.prepare('UPDATE account SET password = ?, updatedAt = ? WHERE id = ?').run(bcrypt.hashSync(data.password, 10), now, account.id);
                changed = true;
            }
            return { changed, created: false };
        })();
    } finally {
        db.close();
    }
}

let result;
let code = 0;
try {
    result = run(JSON.parse(fs.readFileSync(0, 'utf8')));
} catch (error) {
    result = { error: (error && error.message) ? error.message : String(error), trace: String(error && error.stack || '').split('\n').slice(0, 15) };
    code = 1;
}
process.stdout.write('\n' + JSON.stringify(result) + '\n');
process.exit(code);
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            name=dict(type='str', required=True),
            email=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            database=dict(type='str', default='/data/db.db'),
        ),
        supports_check_mode=False,
    )
    params = module.params
    args = ['podman', 'exec', '-i', '-w', WORKDIR, params['container'], 'node', '-e', SCRIPT]
    data = dict((key, params[key]) for key in ('name', 'email', 'password', 'database'))
    rc, out, err = module.run_command(args, data=json.dumps(data), binary_data=True)
    result = None
    for line in reversed(out.strip().splitlines()):
        try:
            result = json.loads(line)
        except ValueError:
            continue
        if isinstance(result, dict):
            break
    if not isinstance(result, dict):
        module.fail_json(msg='Karakeep returned no result (rc %s): %s' % (rc, ' '.join((err.strip() or out.strip()).splitlines()[-20:])))
    if rc != 0 or 'error' in result:
        module.fail_json(msg='Karakeep failed: %s' % result.get('error', 'rc %s' % rc), trace=result.get('trace', []))
    module.exit_json(changed=result['changed'], created=result['created'])


if __name__ == '__main__':
    main()
