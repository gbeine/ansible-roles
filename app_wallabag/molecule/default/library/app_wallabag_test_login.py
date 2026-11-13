#!/usr/bin/python
# -*- coding: utf-8 -*-
# BSD License

from __future__ import absolute_import, division, print_function
__metaclass__ = type

DOCUMENTATION = r'''
---
module: app_wallabag_test_login
short_description: Logs in to wallabag with the login form and opens the administration of the users
description:
  - Reads the login form and its CSRF token, posts the name and the password to /login_check
    and opens /users/list with the session of the login.
  - All requests share one cookie jar and do not follow redirects, Symfony changes the session on the login
    and sets several cookies in the same response.
  - Only reads, it never reports a change.
options:
  url:
    description: The base URL of wallabag, e.g. http://10.89.0.90.
    type: str
    required: true
  name:
    description: The name of the user.
    type: str
    required: true
  password:
    description: The password of the user.
    type: str
    required: true
'''

EXAMPLES = r'''
- name: 'Log in as the administrator'
  app_wallabag_test_login:
    url: 'http://10.89.0.90'
    name: 'molecule-admin'
    password: 'secret-admin-password'
'''

RETURN = r'''
name:
  description: The name of the user.
  returned: always
  type: str
logged_in:
  description: Whether /login_check redirected somewhere else than /login.
  returned: always
  type: bool
location:
  description: The redirect of /login_check.
  returned: always
  type: str
users_page:
  description: The status of /users/list with the session of the login.
  returned: always
  type: int
users_location:
  description: The redirect of /users/list, empty if there is none.
  returned: always
  type: str
'''

import re

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.six.moves import http_cookiejar
from ansible.module_utils.six.moves.urllib import error as urllib_error
from ansible.module_utils.six.moves.urllib import parse as urllib_parse
from ansible.module_utils.six.moves.urllib import request as urllib_request


class NoRedirect(urllib_request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(opener, url, data=None):
    try:
        response = opener.open(url, data=data, timeout=30)
    except urllib_error.HTTPError as e:
        response = e
    status = response.getcode()
    location = response.headers.get('Location') or ''
    body = response.read().decode('utf-8', 'replace')
    return status, location, body


def main():
    module = AnsibleModule(
        argument_spec=dict(
            url=dict(type='str', required=True),
            name=dict(type='str', required=True),
            password=dict(type='str', required=True, no_log=True),
        ),
        supports_check_mode=True,
    )
    base = module.params['url'].rstrip('/')
    opener = urllib_request.build_opener(urllib_request.HTTPCookieProcessor(http_cookiejar.CookieJar()), NoRedirect())

    status, location, body = fetch(opener, base + '/login')
    match = re.search(r'name="_csrf_token"\s+value="([^"]+)"', body)
    if status != 200 or not match:
        module.fail_json(msg='The login form has no CSRF token, status %s' % status)

    data = urllib_parse.urlencode({
        '_username': module.params['name'],
        '_password': module.params['password'],
        '_csrf_token': match.group(1),
    }).encode('utf-8')
    status, location, body = fetch(opener, base + '/login_check', data)
    if status != 302:
        module.fail_json(msg='/login_check answered %s instead of a redirect' % status)
    logged_in = urllib_parse.urlparse(location).path != '/login'

    users_page, users_location, body = fetch(opener, base + '/users/list')
    module.exit_json(changed=False, name=module.params['name'], logged_in=logged_in, location=location,
                     users_page=users_page, users_location=users_location)


if __name__ == '__main__':
    main()
