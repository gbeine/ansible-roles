# Role APT

## Variables

| Variable                                                    | Default         | Comment     |
|-------------------------------------------------------------|-----------------|-------------|
| apt_sources                                                 | []              | See example |
| apt_unattended_upgrades_origin_pattern                      | []              |             |
| apt_conf_languages                                          | ['en']          |             |
| apt_conf_install_recommends                                 | false           |             |
| apt_conf_install_suggests                                   | false           |             |
| apt_conf_periodic_enable                                    | true            |             |
| apt_conf_periodic_unattended_upgrade                        | true            |             |
| apt_conf_periodic_update_package_lists                      | true            |             |
| apt_conf_periodic_download_upgradeable_packages             | true            |             |
| apt_conf_periodic_autoclean_interval                        | 7               |             |
| apt_conf_periodic_verbose                                   | 0               |             |
| apt_unattended_upgrades_auto_fix_interrupted_dpkg           | true            |             |
| apt_unattended_upgrades_minimal_steps                       | true            |             |
| apt_unattended_upgrades_ignore_apps_require_restart         | true            |             |
| apt_unattended_upgrades_install_on_shutdown                 | false           |             |
| apt_unattended_upgrades_mail                                | ''              |             |
| apt_unattended_upgrades_mail_report                         | 'only-on-error' |             |
| apt_unattended_upgrades_remove_unused_kernel_packages       | true            |             |
| apt_unattended_upgrades_remove_new_unused_dependencies      | true            |             |
| apt_unattended_upgrades_remove_unused_dependencies          | false           |             |
| apt_unattended_upgrades_automatic_reboot                    | false           |             |
| apt_unattended_upgrades_automatic_reboot_with_users         | false           |             |
| apt_unattended_upgrades_syslog_enable                       | false           |             |
| apt_unattended_upgrades_syslog_facility                     | 'daemon'        |             |
| apt_unattended_upgrades_only_on_ac_power                    | true            |             |
| apt_unattended_upgrades_skip_updates_on_metered_connections | true            |             |
| apt_unattended_upgrades_verbose                             | false           |             |
| apt_unattended_upgrades_debug                               | false           |             |
| apt_unattended_upgrades_allow_downgrade                     | false           |             |
| apt_unattended_upgrades_allow_apt_mark_fallback             | true            |             |

## Examples

Notes markes with (1)

```
apt_sources:
- name: hetzner (1)
  repos: (2)
  - uri: http://mirror.hetzner.de/debian/packages
    suite: bullseye
    components: [ main, contrib, non-free ]
  - uri: http://mirror.hetzner.de/debian/packages
    suite: bullseye-updates
    components: [ main, contrib, non-free ]
```

* (1) this is the file name under /etc/apt/sources.list.d/
* (2) each file can contain multiple repos following this scheme
