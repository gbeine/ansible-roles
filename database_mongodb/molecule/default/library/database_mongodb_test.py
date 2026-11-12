#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: database_mongodb_test
short_description: Reads the state of MongoDB and tries the accounts of the molecule tests
description:
  - Reads the version, the server parameters, the replica set and the users as root,
    tries listDatabases without login and writes and reads with the accounts app and reader.
  - Writes the document {value 42} to app.molecule with the account app.
options:
  login_host:
    description: The address of MongoDB.
    type: str
    required: true
  login_port:
    description: The port of MongoDB.
    type: int
    default: 27017
  root:
    description: The name and the password of root.
    type: dict
    required: true
    options:
      name:
        type: str
        required: true
        description: The name of root.
      password:
        type: str
        required: true
        description: The password of root.
  parameters:
    description: The server parameters to read.
    type: list
    elements: str
    default: []
  accounts:
    description: The accounts app and reader with name, database and password.
    type: list
    elements: dict
    default: []
    suboptions:
      name:
        type: str
        required: true
        description: The name of the account.
      database:
        type: str
        default: admin
        description: The database of the account.
      password:
        type: str
        required: true
        description: The password of the account.
requirements:
  - pymongo
'''

RETURN = r'''
version:
  description: The version of MongoDB.
  returned: always
  type: str
parameters:
  description: The values of the server parameters.
  returned: always
  type: dict
replica_set:
  description: The name of the replica set, empty without replica set.
  returned: always
  type: str
primary:
  description: Whether MongoDB is the writable primary of the replica set, null without replica set.
  returned: always
  type: bool
users:
  description: The users as database.name.
  returned: always
  type: list
anonymous:
  description: The result of listDatabases without login, allowed or denied with the code.
  returned: always
  type: str
'''

import traceback

from ansible.module_utils.basic import AnsibleModule, missing_required_lib

try:
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure, PyMongoError
    PYMONGO_IMPORT_ERROR = None
except ImportError:
    PYMONGO_IMPORT_ERROR = traceback.format_exc()


def main():
    module = AnsibleModule(
        argument_spec=dict(
            login_host=dict(type='str', required=True),
            login_port=dict(type='int', default=27017),
            root=dict(type='dict', required=True, options=dict(
                name=dict(type='str', required=True),
                password=dict(type='str', required=True, no_log=True),
            )),
            parameters=dict(type='list', elements='str', default=[]),
            accounts=dict(type='list', elements='dict', default=[], options=dict(
                name=dict(type='str', required=True),
                database=dict(type='str', default='admin'),
                password=dict(type='str', required=True, no_log=True),
            )),
        ),
        supports_check_mode=False,
    )
    if PYMONGO_IMPORT_ERROR is not None:
        module.fail_json(msg=missing_required_lib('pymongo'), exception=PYMONGO_IMPORT_ERROR)
    params = module.params

    def client(username=None, password=None, database='admin'):
        return MongoClient(host=params['login_host'], port=params['login_port'], username=username, password=password,
                           authSource=database, directConnection=True, serverSelectionTimeoutMS=10000)

    def attempt(function):
        try:
            function()
            return 'allowed'
        except OperationFailure as error:
            return 'denied: %s' % error.code
        except PyMongoError as error:
            return 'error: %s' % error

    result = dict(changed=False)
    try:
        root = client(params['root']['name'], params['root']['password'])
        result['version'] = root.admin.command('buildInfo')['version']
        result['parameters'] = dict((name, root.admin.command('getParameter', 1, **{name: 1}).get(name)) for name in params['parameters'])
        try:
            result['replica_set'] = root.admin.command('replSetGetStatus')['set']
            result['primary'] = root.admin.command('hello').get('isWritablePrimary', False)
        except OperationFailure:
            result['replica_set'] = ''
            result['primary'] = None
        result['users'] = sorted('%s.%s' % (user['db'], user['user']) for user in root.admin.system.users.find({}, {'user': 1, 'db': 1}))
        root.close()
    except PyMongoError as error:
        module.fail_json(msg='Reading MongoDB as root failed: %s' % error)

    anonymous = client()
    result['anonymous'] = attempt(lambda: anonymous.admin.command('listDatabases'))
    anonymous.close()

    accounts = dict((account['name'], account) for account in params['accounts'])
    if 'app' in accounts:
        app = client(accounts['app']['name'], accounts['app']['password'], accounts['app']['database'])
        result['app_write'] = attempt(lambda: app.app.molecule.insert_one({'value': 42}))
        app.close()
    if 'reader' in accounts:
        reader = client(accounts['reader']['name'], accounts['reader']['password'], accounts['reader']['database'])
        result['reader_read'] = attempt(lambda: reader.app.molecule.find_one({'value': 42}))
        try:
            result['reader_value'] = (reader.app.molecule.find_one({'value': 42}) or {}).get('value')
        except PyMongoError:
            result['reader_value'] = None
        result['reader_write'] = attempt(lambda: reader.app.molecule.insert_one({'value': 43}))
        reader.close()
        wrong = client(accounts['reader']['name'], 'wrong-password', accounts['reader']['database'])
        result['wrong_password'] = attempt(lambda: wrong.admin.command('ping'))
        wrong.close()

    module.exit_json(**result)


if __name__ == '__main__':
    main()
