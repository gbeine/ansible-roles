```yaml
# Set mandatory variables to plausible values
bookstack_home: '/srv/container/bookstack'
bookstack_hostname: 'wiki.example.org'
bookstack_ip: '192.168.99.31'
bookstack_ipv6: 'fd00::99:31'
bookstack_network: 'podman99'
bookstack_timezone: 'Europe/Berlin'
bookstack_uid: 1031

# Configure BookStack with environment variables
# See https://www.bookstackapp.com/docs/ for all available variables
bookstack_environment:
  APP_URL: 'https://wiki.example.org'
  DB_HOST: '192.168.99.30'
  MAIL_DRIVER: 'smtp'
  MAIL_FROM: 'wiki@example.org'
  MAIL_HOST: 'mail.example.org'
  MAIL_PORT: '587'
  MAIL_USERNAME: 'wiki@example.org'
  MAIL_ENCRYPTION: 'tls'
  AUTH_METHOD: 'oidc'
  AUTH_AUTO_INITIATE: 'true'
  OIDC_NAME: 'SSO'
  OIDC_CLIENT_ID: 'bookstack'
  OIDC_ISSUER: 'https://sso.example.org/realms/example'
  OIDC_ISSUER_DISCOVER: 'true'
  SESSION_SECURE_COOKIE: 'true'

# Pass secrets as podman secrets
bookstack_secrets:
  - name: 'bookstack_app_key'
    data: "{{ vault_bookstack_app_key }}"
    target: 'APP_KEY'
  - name: 'bookstack_db_password'
    data: "{{ vault_bookstack_db_password }}"
    target: 'DB_PASSWORD'
  - name: 'bookstack_mail_password'
    data: "{{ vault_bookstack_mail_password }}"
    target: 'MAIL_PASSWORD'
  - name: 'bookstack_oidc_client_secret'
    data: "{{ vault_bookstack_oidc_client_secret }}"
    target: 'OIDC_CLIENT_SECRET'

# Expose BookStack via Traefik
bookstack_labels:
  traefik.enable: 'true'
  traefik.http.routers.bookstack.rule: 'Host(`wiki.example.org`)'
  traefik.http.services.bookstack.loadbalancer.server.port: 80
```
