Place this into `host_vars/hostname/backup.yml`:

```yaml
# Enable backup roles 
backup_enable: true

# Ensure the SSH key is generated 
backup_ssh_enable: true

# Configure Restic backup
backup_restic_enable: true
backup_restic_password: "{{ vault___backup_restic_password }}"
backup_restic_repository: 'sftp:backup:path/to/repository'
backup_restic_ssh: true
backup_restic_host: 'restichost.example.org'
backup_restic_user: 'resticuser'
```
