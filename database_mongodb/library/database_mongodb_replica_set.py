#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: database_mongodb_replica_set
short_description: Initiates a MongoDB replica set with one member
description:
  - Initiates the replica set as the given user if MongoDB is no member of a replica set yet and waits for its primary.
  - Fails if MongoDB is a member of another replica set.
  - community.mongodb.mongodb_replicaset initiates without login, it relies on the localhost exception
    and cannot initiate a replica set of MongoDB with authorization over the network.
options:
  login_host:
    description: The address of MongoDB.
    type: str
    required: true
  login_port:
    description: The port of MongoDB.
    type: int
    default: 27017
  login_user:
    description: The user allowed to initiate the replica set, e.g. root.
    type: str
    required: true
  login_password:
    description: The password of the user.
    type: str
    required: true
  replica_set:
    description: The name of the replica set, replication.replSetName of mongod.
    type: str
    required: true
  member:
    description: The host and port of the only member.
    type: str
    required: true
  timeout:
    description: The seconds to wait for the primary.
    type: int
    default: 60
requirements:
  - pymongo
'''

EXAMPLES = r'''
- name: 'Initiate the replica set'
  database_mongodb_replica_set:
    login_host: '10.89.0.91'
    login_user: 'root'
    login_password: 'secret'
    replica_set: 'rs0'
    member: '10.89.0.91:27017'
'''

RETURN = r'''
replica_set:
  description: The name of the replica set.
  returned: always
  type: str
'''

import time
import traceback

from ansible.module_utils.basic import AnsibleModule, missing_required_lib

try:
    from pymongo import MongoClient
    from pymongo.errors import PyMongoError
    PYMONGO_IMPORT_ERROR = None
except ImportError:
    PYMONGO_IMPORT_ERROR = traceback.format_exc()


def main():
    module = AnsibleModule(
        argument_spec=dict(
            login_host=dict(type='str', required=True),
            login_port=dict(type='int', default=27017),
            login_user=dict(type='str', required=True),
            login_password=dict(type='str', required=True, no_log=True),
            replica_set=dict(type='str', required=True),
            member=dict(type='str', required=True),
            timeout=dict(type='int', default=60),
        ),
        supports_check_mode=True,
    )
    if PYMONGO_IMPORT_ERROR is not None:
        module.fail_json(msg=missing_required_lib('pymongo'), exception=PYMONGO_IMPORT_ERROR)

    params = module.params
    client = MongoClient(host=params['login_host'], port=params['login_port'], username=params['login_user'],
                         password=params['login_password'], authSource='admin', directConnection=True,
                         serverSelectionTimeoutMS=10000)
    try:
        name = client.admin.command('hello').get('setName')
        if name is not None and name != params['replica_set']:
            module.fail_json(msg='MongoDB is a member of the replica set %s, not of %s.' % (name, params['replica_set']))
        changed = name is None
        if changed and not module.check_mode:
            client.admin.command('replSetInitiate', {'_id': params['replica_set'], 'members': [{'_id': 0, 'host': params['member']}]})
            for _ in range(params['timeout']):
                if client.admin.command('hello').get('isWritablePrimary'):
                    break
                time.sleep(1)
            else:
                module.fail_json(msg='The replica set %s has no primary after %s seconds.' % (params['replica_set'], params['timeout']))
    except PyMongoError as error:
        module.fail_json(msg='The replica set %s failed: %s' % (params['replica_set'], error))
    finally:
        client.close()

    module.exit_json(changed=changed, replica_set=params['replica_set'])


if __name__ == '__main__':
    main()
