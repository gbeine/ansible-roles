#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_joplin_admin
short_description: Creates the administrator of Joplin Server and keeps its password, email and name up to date
description:
  - Runs node in the container of Joplin Server with the models of Joplin Server, the configuration of the database
    comes from the environment of the container. The email, the password and the name are passed on stdin,
    they are never arguments of a process.
  - Looks up the user by its email. If it does not exist, the administrator admin@localhost created by the first migration
    is taken over and gets the email, so no administrator with the default password remains. Otherwise the user is created.
  - Checks the password with checkPassword of Joplin Server and only sets it if it differs,
    Joplin Server rejects weak passwords then.
  - Makes the user an enabled administrator with a confirmed email.
options:
  container:
    description: The name of the container of Joplin Server.
    type: str
    required: true
  email:
    description: The email address of the administrator, Joplin Server identifies users by it.
    type: str
    required: true
  password:
    description: The password of the administrator.
    type: str
    required: true
  full_name:
    description: The full name of the administrator, it is not changed if it is not set.
    type: str
    required: false
  default_email:
    description: The email of the administrator created by the first migration of Joplin Server.
    type: str
    default: admin@localhost
'''

EXAMPLES = r'''
- name: 'Create the administrator'
  app_joplin_admin:
    container: 'joplin'
    email: 'admin@example.org'
    password: 'secret-admin-password'
    full_name: 'Administrator'
'''

RETURN = r'''
created:
  description: Whether the administrator was created.
  returned: always
  type: bool
taken_over:
  description: Whether the administrator created by the first migration got the email.
  returned: always
  type: bool
'''

import json

from ansible.module_utils.basic import AnsibleModule

# Reads {email, password, full_name, default_email} from stdin, uses the modules of dist/ like app.ts
ADMIN = r'''
const fs = require('fs');
const { shimInit } = require('@joplin/lib/shim-init-node');
shimInit({ nodeSqlite: require('sqlite3') });
const { parseEnv } = require('./dist/env');
const configModule = require('./dist/config');
const { connectDb, disconnectDb, sqliteDefaultDir } = require('./dist/db');
const newModelFactory = require('./dist/models/factory').default;
const { checkPassword } = require('./dist/utils/auth');

const main = async () => {
    const data = JSON.parse(fs.readFileSync(0, 'utf8'));
    await configModule.initConfig('prod', parseEnv(process.env, { SQLITE_DATABASE: sqliteDefaultDir + '/db-prod.sqlite' }));
    const config = configModule.default();
    const db = await connectDb(config.database);
    try {
        const users = newModelFactory(db, db, config).user();
        let user = await users.loadByEmail(data.email);
        let created = false;
        let takenOver = false;
        const changes = {};
        if (!user) {
            user = await users.loadByEmail(data.default_email);
            if (user) {
                changes.email = data.email;
                takenOver = true;
            }
        }
        if (!user) {
            const fields = { email: data.email, password: data.password, is_admin: 1, enabled: 1, email_confirmed: 1, must_set_password: 0 };
            if (data.full_name !== null) fields.full_name = data.full_name;
            await users.save(fields);
            created = true;
        } else {
            if (!(await checkPassword(data.password, user.password || ''))) changes.password = data.password;
            for (const [key, value] of [['is_admin', 1], ['enabled', 1], ['email_confirmed', 1], ['must_set_password', 0]]) {
                if (Number(user[key]) !== value) changes[key] = value;
            }
            if (data.full_name !== null && (user.full_name || '') !== data.full_name) changes.full_name = data.full_name;
            if (Object.keys(changes).length > 0) await users.save({ id: user.id, ...changes });
        }
        const changed = created || Object.keys(changes).length > 0;
        process.stdout.write('\n' + JSON.stringify({ changed, created, taken_over: takenOver }) + '\n');
    } finally {
        await disconnectDb(db);
    }
};

main().then(() => process.exit(0), (error) => {
    process.stderr.write((error && error.message ? error.message : String(error)) + '\n');
    process.exit(1);
});
'''


def main():
    module = AnsibleModule(
        argument_spec=dict(
            container=dict(type='str', required=True),
            email=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
            full_name=dict(type='str', required=False, default=None),
            default_email=dict(type='str', default='admin@localhost'),
        ),
        supports_check_mode=False,
    )
    params = module.params
    args = ['podman', 'exec', '-i', '-w', '/home/joplin/packages/server', params['container'], 'node', '-e', ADMIN]
    data = dict((key, params[key]) for key in ('email', 'password', 'full_name', 'default_email'))
    rc, out, err = module.run_command(args, data=json.dumps(data), binary_data=True)
    if rc != 0:
        module.fail_json(msg='Joplin Server failed: %s' % (err.strip() or out.strip()))
    try:
        result = json.loads(out.strip().splitlines()[-1])
    except (ValueError, IndexError, KeyError):
        module.fail_json(msg='Joplin Server returned no result: %s %s' % (out.strip(), err.strip()))
    module.exit_json(changed=result['changed'], created=result['created'], taken_over=result['taken_over'])


if __name__ == '__main__':
    main()
