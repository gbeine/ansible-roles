# Role MYSQL

## Variables

| Variable                      | Default                                                               | Comment |
|-------------------------------|-----------------------------------------------------------------------|---------|
| backup_enable                 | false                                                                 |         |
| backup_logfile                | '/var/log/backup-daily.log'                                           |         |
| backup_error_logfile          | '/var/log/backup-error.log'                                           |         |
| backup_target_directory       | '/mnt/backup'                                                         |         |
| backup_nfs_client_enable      | false                                                                 |         |
| backup_nfs_client_src         | ''                                                                    |         |
| backup_ssh_client_enable      | false                                                                 |         |
| backup_ssh_user               | 'backup'                                                              |         |
| backup_ssh_key_size           | 4096                                                                  |         |
| backup_ssh_key_name           | 'backup'                                                              |         |
| backup_ssh_comment            | 'backup over SSH'                                                     |         |
| vault__backup_ssh_password    | ''                                                                    |         |
| backup_borg_enable            | false                                                                 |         |
| backup_borg_rsh               | 'ssh -i ~/.ssh/{{ backup__ssh_key_name }} -oStrictHostKeyChecking=no' |         |
| backup_borg_backup_dir        | {{ backup__target_directory }}                                        |         |
| backup_borg_cache_dir         | ''                                                                    |         |
| backup_borg_options           | '-s -v -p'                                                            |         |
| backup_borg_include           | [ '/etc', '/home', '/root', '/usr/local/etc', '/var/log' ]            |         |
| backup_borg_exclude           | []                                                                    |         |
| vault__backup_borg_password   | ''                                                                    |         |
| backup_mysql_enable           | false                                                                 |         |
| backup_mysql_compress         | true                                                                  |         |
| backup_mysql_replication      | false                                                                 |         |
| backup_mysql_backup_dir       | '/var/backup/mysql'                                                   |         |
| backup_mysql_host             | 'localhost'                                                           |         |
| backup_mysql_user             | '_backup_'                                                            |         |
| backup_mysql_ignore_databases | [ 'information_schema', 'performance_schema', 'sys' ]                 |         |
| backup_mysql_keep_days        | '14'                                                                  |         |
| vault__backup_mysql_password  | ''                                                                    |         |

## Examples
