#!/usr/bin/python
# -*- coding: utf-8 -*-

# BSD License

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r'''
---
module: security_pocketid_api
short_description: Manages the admin, the groups, the users and the OIDC clients of Pocket ID
description:
  - Uses the API of Pocket ID with the static API key (header C(X-API-Key)).
  - Creates the first admin once, an existing admin keeps its values and is only made an admin again.
  - Manages the listed groups, users and clients, entries with C(state=absent) are removed, other entries are not touched.
  - Compares every listed value with Pocket ID and only reports a change if it changed something.
  - The secret of a client is checked with the introspection endpoint and HTTP Basic, an unknown secret is created and replaces the former secrets.
options:
  url:
    description: The URL of Pocket ID, e.g. C(http://10.0.0.1:1411).
    type: str
    required: true
  api_key:
    description: The static API key of Pocket ID (C(STATIC_API_KEY)).
    type: str
    required: true
    no_log: true
  validate_certs:
    description: Validate the certificate of Pocket ID.
    type: bool
    default: false
  admin:
    description: The first admin with C(username) and optionally C(email), C(first_name), C(last_name), C(display_name) and C(locale).
    type: dict
    required: true
  groups:
    description: The groups with C(name), optionally C(friendly_name) (default the name) and C(state).
    type: list
    elements: dict
    default: []
  users:
    description:
      - The users with C(username), optionally C(email), C(first_name), C(last_name), C(display_name), C(locale), C(admin), C(disabled),
        C(groups) (the names of the groups) and C(state).
    type: list
    elements: dict
    default: []
  clients:
    description:
      - The OIDC clients with C(id) and C(name), optionally C(description), C(callback_urls), C(logout_callback_urls), C(launch_url), C(public),
        C(pkce), C(skip_consent), C(requires_reauthentication), C(groups) (the names of the allowed groups), C(secret) and C(state).
    type: list
    elements: dict
    default: []
author:
  - Gerrit Beine
'''

EXAMPLES = r'''
- name: Manage Pocket ID
  security_pocketid_api:
    url: 'http://10.89.0.130:1411'
    api_key: "{{ vault_pocketid_api_key }}"
    admin:
      username: 'admin'
      email: 'admin@example.org'
    groups:
      - name: 'grafana-admins'
        friendly_name: 'Grafana Admins'
    users:
      - username: 'jane'
        email: 'jane@example.org'
        groups: [ 'grafana-admins' ]
    clients:
      - id: 'grafana'
        name: 'Grafana'
        callback_urls: [ 'https://grafana.example.org/login/generic_oauth' ]
        groups: [ 'grafana-admins' ]
        secret: "{{ vault_grafana_client_secret }}"
'''

RETURN = r'''
changes:
  description: The changes, e.g. C(created group grafana-admins).
  returned: always
  type: list
  elements: str
'''

import base64
import json
import ssl

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves.urllib.error import HTTPError, URLError
from ansible.module_utils.six.moves.urllib.parse import quote, urlencode
from ansible.module_utils.six.moves.urllib.request import Request, build_opener, HTTPSHandler


# The fields of the API and the keys of the role
USER_FIELDS = {
    'email': 'email',
    'first_name': 'firstName',
    'last_name': 'lastName',
    'display_name': 'displayName',
    'locale': 'locale',
    'admin': 'isAdmin',
    'disabled': 'disabled',
}

CLIENT_FIELDS = {
    'name': 'name',
    'description': 'description',
    'callback_urls': 'callbackURLs',
    'logout_callback_urls': 'logoutCallbackURLs',
    'launch_url': 'launchURL',
    'public': 'isPublic',
    'pkce': 'pkceEnabled',
    'skip_consent': 'skipConsent',
    'requires_reauthentication': 'requiresReauthentication',
}

# The fields of OidcClientUpdateDto, a PUT replaces the client, the fields not managed by the role keep their values
CLIENT_UPDATE_FIELDS = [
    'name', 'description', 'callbackURLs', 'logoutCallbackURLs', 'backchannelLogoutURL', 'isPublic', 'pkceEnabled',
    'requiresReauthentication', 'requiresPushedAuthorizationRequests', 'skipConsent', 'credentials', 'launchURL',
    'hasLogo', 'hasDarkLogo', 'isGroupRestricted', 'accessTokenDurationMinutes', 'refreshTokenDurationMinutes',
]

# The fields of UserCreateDto, a PUT replaces the user, the fields not managed by the role keep their values
USER_UPDATE_FIELDS = ['username', 'email', 'emailVerified', 'firstName', 'lastName', 'displayName', 'isAdmin', 'locale', 'disabled']


class PocketID(object):

    def __init__(self, module):
        self.module = module
        self.url = module.params['url'].rstrip('/')
        self.api_key = module.params['api_key']
        context = ssl.create_default_context()
        if not module.params['validate_certs']:
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
        self.opener = build_opener(HTTPSHandler(context=context))
        self.changes = []

    def request(self, method, path, body=None, headers=None, form=None, expected=(200, 201, 204)):
        data = None
        request_headers = {'Accept': 'application/json'}
        if form is not None:
            data = urlencode(form).encode('utf-8')
            request_headers['Content-Type'] = 'application/x-www-form-urlencoded'
        elif body is not None:
            data = json.dumps(body).encode('utf-8')
            request_headers['Content-Type'] = 'application/json'
        if headers is None:
            request_headers['X-API-Key'] = self.api_key
        else:
            request_headers.update(headers)
        request = Request(self.url + path, data=data, headers=request_headers)
        request.get_method = lambda: method
        try:
            response = self.opener.open(request, timeout=30)
            status = response.getcode()
            content = response.read()
        except HTTPError as error:
            status = error.code
            content = error.read()
        except URLError as error:
            self.module.fail_json(msg='Pocket ID does not answer on %s: %s' % (self.url, error.reason), changes=self.changes)
        if status not in expected:
            self.module.fail_json(msg='%s %s answered %s: %s' % (method, path, status, content.decode('utf-8', 'replace')), changes=self.changes)
        if not content:
            return status, None
        try:
            return status, json.loads(content.decode('utf-8'))
        except ValueError:
            return status, None

    def list_all(self, path):
        items = []
        page = 1
        while True:
            separator = '&' if '?' in path else '?'
            _, result = self.request('GET', '%s%spagination[page]=%d&pagination[limit]=100' % (path, separator, page))
            items.extend(result.get('data') or [])
            total = (result.get('pagination') or {}).get('totalPages', 1)
            if page >= total:
                return items
            page += 1

    def change(self, message):
        self.changes.append(message)

    def write(self, method, path, body=None):
        if self.module.check_mode:
            return {}
        return self.request(method, path, body)[1] or {}

    # Groups

    def groups(self, groups):
        existing = dict((group['name'], group) for group in self.list_all('/api/user-groups'))
        for group in groups:
            name = group['name']
            if group.get('state', 'present') == 'absent':
                continue
            friendly_name = group.get('friendly_name') or name
            if name not in existing:
                created = self.write('POST', '/api/user-groups', {'name': name, 'friendlyName': friendly_name})
                existing[name] = {'id': created.get('id', name), 'name': name, 'friendlyName': friendly_name}
                self.change('created group %s' % name)
            elif existing[name].get('friendlyName') != friendly_name:
                self.write('PUT', '/api/user-groups/%s' % quote(existing[name]['id']), {'name': name, 'friendlyName': friendly_name})
                self.change('updated group %s' % name)
        return dict((name, group['id']) for name, group in existing.items())

    def remove_groups(self, groups, group_ids):
        for group in groups:
            if group.get('state', 'present') == 'absent' and group['name'] in group_ids:
                self.write('DELETE', '/api/user-groups/%s' % quote(group_ids[group['name']]))
                self.change('removed group %s' % group['name'])

    # Users

    def users(self, admin, users, group_ids):
        existing = dict((user['username'], user) for user in self.list_all('/api/users'))

        # The admin is created once and only made an admin again, its other values belong to Pocket ID
        username = admin['username']
        if username not in existing:
            body = {'username': username, 'isAdmin': True}
            for key, field in USER_FIELDS.items():
                if admin.get(key) is not None:
                    body[field] = admin[key]
            body['isAdmin'] = True
            created = self.write('POST', '/api/users', body)
            existing[username] = created or body
            self.change('created admin %s' % username)
        elif not existing[username].get('isAdmin'):
            self.update_user(existing[username], {'isAdmin': True})
            self.change('made %s an admin' % username)

        for user in users:
            username = user['username']
            current = existing.get(username)
            if user.get('state', 'present') == 'absent':
                if current is not None:
                    self.write('DELETE', '/api/users/%s' % quote(current['id']))
                    self.change('removed user %s' % username)
                continue
            wanted = dict((field, user[key]) for key, field in USER_FIELDS.items() if key in user and user[key] is not None)
            wanted_groups = [group_ids[name] for name in user.get('groups') or [] if name in group_ids]
            if current is None:
                body = dict(wanted, username=username, userGroupIds=wanted_groups)
                body.setdefault('displayName', ' '.join(part for part in [user.get('first_name'), user.get('last_name')] if part) or username)
                self.write('POST', '/api/users', body)
                self.change('created user %s' % username)
                continue
            if any(current.get(field) != value for field, value in wanted.items()):
                self.update_user(current, wanted)
                self.change('updated user %s' % username)
            if 'groups' in user:
                current_groups = sorted(group['id'] for group in current.get('userGroups') or [])
                if current_groups != sorted(wanted_groups):
                    self.write('PUT', '/api/users/%s/user-groups' % quote(current['id']), {'userGroupIds': wanted_groups})
                    self.change('updated the groups of user %s' % username)

    def update_user(self, current, wanted):
        body = dict((field, current.get(field)) for field in USER_UPDATE_FIELDS if field in current)
        body.update(wanted)
        for field in ['email', 'locale', 'lastName']:
            if body.get(field) == '':
                body[field] = None
        self.write('PUT', '/api/users/%s' % quote(current['id']), body)

    # Clients

    def clients(self, clients, group_ids):
        existing = dict((client['id'], client) for client in self.list_all('/api/oidc/clients'))
        for client in clients:
            client_id = client['id']
            current = existing.get(client_id)
            if client.get('state', 'present') == 'absent':
                if current is not None:
                    self.write('DELETE', '/api/oidc/clients/%s' % quote(client_id))
                    self.change('removed client %s' % client_id)
                continue
            wanted = dict((field, client[key]) for key, field in CLIENT_FIELDS.items() if key in client and client[key] is not None)
            if 'groups' in client:
                wanted['isGroupRestricted'] = len(client['groups'] or []) > 0
            if current is None:
                body = dict({'callbackURLs': [], 'logoutCallbackURLs': []}, **wanted)
                body['id'] = client_id
                self.write('POST', '/api/oidc/clients', body)
                self.change('created client %s' % client_id)
                current = None if self.module.check_mode else self.request('GET', '/api/oidc/clients/%s' % quote(client_id))[1]
            else:
                current = self.request('GET', '/api/oidc/clients/%s' % quote(client_id))[1]
                if any(self.differs(current.get(field), value) for field, value in wanted.items()):
                    body = dict((field, current.get(field)) for field in CLIENT_UPDATE_FIELDS if field in current)
                    body.update(wanted)
                    self.write('PUT', '/api/oidc/clients/%s' % quote(client_id), body)
                    self.change('updated client %s' % client_id)
            if current is None:
                continue
            if 'groups' in client:
                wanted_groups = sorted(group_ids[name] for name in client['groups'] or [] if name in group_ids)
                current_groups = sorted(group['id'] for group in current.get('allowedUserGroups') or [])
                if current_groups != wanted_groups:
                    self.write('PUT', '/api/oidc/clients/%s/allowed-user-groups' % quote(client_id), {'userGroupIds': wanted_groups})
                    self.change('updated the groups of client %s' % client_id)
            if client.get('secret') and not client.get('public', False):
                self.secret(client_id, client['secret'])

    @staticmethod
    def differs(current, wanted):
        if isinstance(wanted, list):
            return list(current or []) != wanted
        if wanted == '' and current is None:
            return False
        return current != wanted

    # The introspection authenticates the client with HTTP Basic first, a wrong secret answers 401,
    # the right one 200 with an inactive token, other answers stop the module
    def secret_known(self, client_id, secret):
        credentials = base64.b64encode(('%s:%s' % (quote(client_id, safe=''), quote(secret, safe=''))).encode('utf-8')).decode('ascii')
        status, _ = self.request('POST', '/api/oidc/introspect', form={'token': 'security-pocketid-check'},
                                 headers={'Authorization': 'Basic ' + credentials, 'Accept': 'application/json'},
                                 expected=(200, 401))
        return status == 200

    def secret(self, client_id, secret):
        if self.secret_known(client_id, secret):
            return
        former = self.request('GET', '/api/oidc/clients/%s/secrets' % quote(client_id))[1] or []
        if isinstance(former, dict):
            former = former.get('data') or []
        created = self.write('POST', '/api/oidc/clients/%s/secrets' % quote(client_id), {'secret': secret})
        for entry in former:
            if entry.get('id') and entry.get('id') != created.get('id'):
                self.write('DELETE', '/api/oidc/clients/%s/secrets/%s' % (quote(client_id), quote(entry['id'])))
        self.change('replaced the secret of client %s' % client_id)


def main():
    module = AnsibleModule(
        argument_spec=dict(
            url=dict(type='str', required=True),
            api_key=dict(type='str', required=True, no_log=True),
            validate_certs=dict(type='bool', default=False),
            admin=dict(type='dict', required=True),
            groups=dict(type='list', elements='dict', default=[]),
            users=dict(type='list', elements='dict', default=[]),
            clients=dict(
                type='list', elements='dict', default=[],
                options=dict(
                    id=dict(type='str', required=True),
                    name=dict(type='str'),
                    description=dict(type='str'),
                    callback_urls=dict(type='list', elements='str'),
                    logout_callback_urls=dict(type='list', elements='str'),
                    launch_url=dict(type='str'),
                    public=dict(type='bool'),
                    pkce=dict(type='bool'),
                    skip_consent=dict(type='bool'),
                    requires_reauthentication=dict(type='bool'),
                    groups=dict(type='list', elements='str'),
                    secret=dict(type='str', no_log=True),
                    state=dict(type='str', default='present', choices=['present', 'absent']),
                ),
            ),
        ),
        supports_check_mode=True,
    )

    # Options without value are left out, the role only compares the listed values
    clients = [dict((key, value) for key, value in client.items() if value is not None) for client in module.params['clients']]

    api = PocketID(module)
    group_ids = api.groups(module.params['groups'])
    api.users(module.params['admin'], module.params['users'], group_ids)
    api.clients(clients, group_ids)
    api.remove_groups(module.params['groups'], group_ids)

    module.exit_json(changed=len(api.changes) > 0, changes=api.changes)


if __name__ == '__main__':
    main()
