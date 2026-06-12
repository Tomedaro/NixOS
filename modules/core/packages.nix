{ pkgs, ... }:
{
  # TODO: review
  programs = {
    fuse.userAllowOther = true;
    mtr.enable = true;
    gnupg.agent = {
      enable = true;
      enableSSHSupport = true;
    };
    zoxide = {
      enable = true;
      enableZshIntegration = true;
      flags = [ "--cmd cd" ];
    };
  };

  nixpkgs.config = {
    allowUnfree = true;
    permittedInsecurePackages = [
      "ventoy-1.1.12"
    ];
  };

  environment.systemPackages = with pkgs; [
    appimage-run # Needed For AppImage Support
    killall # For Killing All Instances Of Programs
    lm_sensors # Used For Getting Hardware Temps
    gnome-disk-utility # Disk Partitioning and Mounting Utility
    rclone # Cloning Utility
    jq # Json Formatting Utility
    bibata-cursors
    sddm-astronaut # Sddm Theme (Overlayed)
    kdePackages.qtsvg # Sddm Dependency
    kdePackages.qtmultimedia # Sddm Dependency
    kdePackages.qtvirtualkeyboard # Sddm Dependency
    fzf # Fuzzy Finder
    fd # Better Find
    git # Git
    gh # Github Authentication Client
    libjxl # Support for JXL Images
    microfetch # Small fetch (Blazingly fast)
    nix-prefetch-scripts # Find Hashes/Revisions of Nix Packages
    ripgrep # Improved Grep
    tldr # Improved Man
    unrar # Tool For Handling .rar Files
    unzip # Tool For Handling .zip Files

  ];
}
