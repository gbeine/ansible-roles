#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: database_mongodb_logins
short_description: Checks the logins of MongoDB accounts
description:
  - Logs in with every account and returns the names of the accounts that cannot log in.
  - MongoDB cannot compare passwords, the role sets the password only for accounts that cannot log in.
  - Changes nothing.
options:
  login_host:
    description: The address of MongoDB.
    type: str
    required: true
  login_port:
    description: The port of MongoDB.
    type: int
    default: 27017
  accounts:
    description: The accounts to check.
    type: list
    elements: dict
    required: true
    suboptions:
      name:
        description: The name of the account.
        type: str
        required: true
      database:
        description: The database of the account.
        type: str
        default: admin
      password:
        description: The password of the account.
        type: str
        required: true
requirements:
  - pymongo
'''

EXAMPLES = r'''
- name: 'Check the logins'
  database_mongodb_logins:
    login_host: '10.89.0.90'
    accounts:
      - { name: 'root', database: 'admin', password: 'secret' }
  register: 'logins'
'''

RETURN = r'''
failed_logins:
  description: The names of the accounts that cannot log in.
  returned: always
  type: list
  elements: str
'''

import traceback

from ansible.module_utils.basic import AnsibleModule, missing_required_lib

try:
    from pymongo import MongoClient
    from pymongo.errors import OperationFailure, PyMongoError
    PYMONGO_IMPORT_ERROR = None
except ImportError:
    PYMONGO_IMPORT_ERROR = traceback.format_exc()

AUTHENTICATION_FAILED = 18


def main():
    module = AnsibleModule(
        argument_spec=dict(
            login_host=dict(type='str', required=True),
            login_port=dict(type='int', default=27017),
            accounts=dict(type='list', elements='dict', required=True, options=dict(
                name=dict(type='str', required=True),
                database=dict(type='str', default='admin'),
                password=dict(type='str', required=True, no_log=True),
            )),
        ),
        supports_check_mode=True,
    )
    if PYMONGO_IMPORT_ERROR is not None:
        module.fail_json(msg=missing_required_lib('pymongo'), exception=PYMONGO_IMPORT_ERROR)

    failed = []
    for account in module.params['accounts']:
        client = MongoClient(host=module.params['login_host'], port=module.params['login_port'],
                             username=account['name'], password=account['password'], authSource=account['database'],
                             directConnection=True, serverSelectionTimeoutMS=10000)
        try:
            client.admin.command('ping')
        except OperationFailure as error:
            if error.code != AUTHENTICATION_FAILED:
                module.fail_json(msg='The login of %s failed: %s' % (account['name'], error))
            failed.append(account['name'])
        except PyMongoError as error:
            module.fail_json(msg='MongoDB is not reachable: %s' % error)
        finally:
            client.close()

    module.exit_json(changed=False, failed_logins=failed)


if __name__ == '__main__':
    main()
