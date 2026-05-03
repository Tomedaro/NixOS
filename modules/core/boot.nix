{ pkgs, ... }:
{
  boot = {
    supportedFilesystems = [ "ntfs" "exfat" "ext4" "fat32" "btrfs" ];
    tmp.cleanOnBoot = true;
    kernelPackages = pkgs.linuxPackages_latest;
    kernelParams = [ "preempt=full" ];
    loader = {
      efi.canTouchEfiVariables = true;
      efi.efiSysMountPoint = "/boot";
      timeout = null;
      grub = {
        enable = true;
        device = "nodev";
        efiSupport = true;
        useOSProber = false; # Manual entry below is more reliable
        gfxmodeEfi = "1920x1080"; # Change to 2715x1527 if you have HiDPI
        gfxmodeBios = "1920x1080";
        extraEntries = ''
          menuentry "Arch Linux" {
            search --no-floppy --fs-uuid --set=root 0b608695-3b2f-4dd6-a56a-c5ce7dc8a7cd
            echo 'Loading Arch Linux...'
            linux /vmlinuz-linux root=UUID=0b608695-3b2f-4dd6-a56a-c5ce7dc8a7cd rw quiet loglevel=3
            initrd /initramfs-linux.img
          }
        '';
        theme = pkgs.stdenv.mkDerivation {
          pname = "distro-grub-themes";
          version = "3.1";
          src = pkgs.fetchFromGitHub {
            owner = "AdisonCavani";
            repo = "distro-grub-themes";
            rev = "v3.1";
            hash = "sha256-ZcoGbbOMDDwjLhsvs77C7G7vINQnprdfI37a9ccrmPs=";
          };
          installPhase = "cp -r customize/nixos $out";
        };
      };
    };
    # binfmt.registrations.appimage = {
    #   wrapInterpreterInShell = false;
    #   interpreter = "${pkgs.appimage-run}/bin/appimage-run";
    #   recognitionType = "magic";
    #   offset = 0;
    #   mask = ''\\xff\\xff\\xff\\xff\\x00\\x00\\x00\\x00\\xff\\xff\\xff'';
    #   magicOrExtension = ''\\x7fELF....AI\\x02'';
    # };
  };
}
