{...}: {
  boot.loader.grub.extraEntries = ''
    menuentry "Arch Linux" {
      search --no-floppy --fs-uuid --set=root 0b608695-3b2f-4dd6-a56a-c5ce7dc8a7cd
      echo 'Loading Arch Linux...'
      linux /vmlinuz-linux root=UUID=0b608695-3b2f-4dd6-a56a-c5ce7dc8a7cd rw quiet loglevel=3
      initrd /initramfs-linux.img
    }
  '';
}
