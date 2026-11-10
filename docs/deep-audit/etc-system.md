# System configuration and boot continuation

Read-only package backup inspection found16modified packaged configuration files; etc-modified-coverage.json records27path reads/classifications including11followed boot/SSH/SDDM/sysctl inputs. Four account/subordinate-ID tables are structural identity allocations, not copied. OpenFortiVPN login/trust assignments are withheld. The package backup list excludes unowned files and does not prove every /etc file was customized or reviewed.

## ES001 — Boot reality is GRUB plus generated ESP automount

Current /proc/cmdline selects vmlinuz-linux-lts and ext4 NVMe root by UUID, rw, loglevel3 quiet. /etc/fstab contains only an ext4 VM disk at /mnt/vms; root therefore cannot be reconstructed from that file alone. Current findmnt confirms root on NVMe partition2, EFI /boot on partition1 and VM disk on sda1. systemctl cat boot.automount/boot.mount identifies systemd-gpt-auto-generator output,120second idle automount and vfat masks/nodev/nosuid/noexec/nosymfollow. A filesystem lookup can activate this ordinary automount, so read-only inspection does not mean the OS's mount state is frozen. No mount command or persistent mount change was issued.

The fully read generated /boot/grub/grub.cfg defaults to entry0: linux-lts, Intel microcode plus LTS initramfs; Advanced also offers linux. Both kernel presets build only default initramfs, with fallback variants commented. /etc/default/grub sets5second graphical menu,auto resolution/keep payload,quiet loglevel3,recovery disabled and no configured theme/background. /etc/mkinitcpio.conf uses systemd/autodetect/microcode/modconf/kms/keyboard/sd-vconsole/block/filesystems/fsck. No plymouth hook is present in that list. Thus a large retained Plymouth theme catalogue does not establish an active boot splash. /boot/loader is absent; this is not a systemd-boot conclusion based solely on directory naming. Custom grub source scripts are stock empty/source-if-present templates, and grub/custom.cfg is absent. No reboot or boot acceptance test performed.

## ES002 — Networking and SSH have distinct persistent inputs

Tailscale generates resolv.conf with its DNS addresses/search suffix;99-tailscale.sysctl enables IPv4/IPv6 forwarding. /etc/hosts carries several loopback local-development names plus two tailnet development/production aliases. These are local resolution/forwarding inputs, not evidence those projects or tunnels are serving. Existing mobile/VPN interface state was untouched.

sshd_config includes drop-ins, explicitly allows password authentication and prohibits root password login, and selects .ssh/authorized_keys.99-archlinux.conf disables keyboard-interactive auth,enables PAM and disables PrintMotd. These are combined source settings; no sshd reload, remote connection or effective-config acceptance performed. OpenFortiVPN has retained workplace endpoint/port and login/trust assignments; no VPN was launched.

## ES003 — Packaged modification markers do not identify intent alone

Gluster daemon volume config sets socket management port24007,max60999,one event thread; libvirt/network.conf's backend line remains commented, leaving selection to runtime defaults. Cursor sysctl file's AppArmor options are also both commented. A pacman modified marker may reflect package/generated drift rather than an intentional active override. Reflector mirrorlist is dated April29with regional mirrors. TeX format table is generated from installed package declarations and explicitly warns against manual edits. TPM FAPI profiles describe ECC384/RSA3072+SHA384/AES256CFB,PCR and endorsement policy metadata; they contain public templates/policy digests, not extracted device private keys or proof of TPM usage. No formatter, TPM, virtualization or storage command was invoked.
