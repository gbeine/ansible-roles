Place this into `host_vars/hostname/backup.yml`:

```yaml
# Enable backup roles 
backup_enable: true

# Ensure the SSH key is generated 
backup_ssh_enable: true

# Configure Restic backup
backup_borg_enable: true
backup_borg_password: "{{ vault___backup_borg_password }}"
backup_borg_repository: 'ssh://backupuser@backuphost.example.org:23/./borgbackup'
```
