{ pkgs, inputs, ... }:
{
  environment.systemPackages = with pkgs; [
    # Personal tools
    captive-browser
    qimgv
    killall
    android-tools
    feh
    foliate
    sioyek
    lm_sensors
    guvcview
    jq
    bibata-cursors
    sddm-astronaut        # Overlayed
    pkgs.kdePackages.qtsvg
    pkgs.kdePackages.qtmultimedia
    pkgs.kdePackages.qtvirtualkeyboard

    # From flake inputs
    inputs.bzmenu.packages.${pkgs.system}.default
    inputs.yt-x.packages.${pkgs.system}.default
    inputs.zen-browser.packages.${pkgs.system}.default

    # Dev tools
    obsidian
    ludusavi
    proton-vpn
    github-desktop
    # pokego # Overlayed
  ];

  # Personal home packages via home-manager
  home-manager.sharedModules = [
    (_: {
      home.packages = with pkgs; [
        # Applications
        anki-bin
        qbittorrent
        telegram-desktop
        zoom-us
        google-chrome
        protonup-qt
        steam

        # Terminal tools
        fuzzel
        cool-retro-term
        fzf
        fd
        git
        gh
        htop
        nix-prefetch-scripts
        microfetch
        ripgrep
        tldr
        unzip
        grim
        bun

        # Creative
        krita
        vlc
        gimp
      ];
    })
  ];
}
