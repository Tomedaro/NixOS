{ pkgs, inputs, ... }:

let
  # Create a custom wrapped version of Anki
  anki-wayland-fixed = pkgs.symlinkJoin {
    name = "anki";
    paths = [ pkgs.anki-bin ];
    buildInputs = [ pkgs.makeWrapper ];
    postBuild = ''
      wrapProgram $out/bin/anki \
        --set QTWEBENGINE_CHROMIUM_FLAGS "--no-sandbox"
    '';
  };
in

{
  environment.systemPackages = with pkgs; [
    # Personal tools
    easyeffects
    anki-wayland-fixed
    captive-browser
    bleachbit
    qimgv
    killall
    android-tools
    feh
    foliate
    sioyek
    lm_sensors
    guvcview
    jq
    sedutil
    bibata-cursors
    sddm-astronaut        # Overlayed
    pkgs.kdePackages.qtsvg
    pkgs.kdePackages.qtmultimedia
    pkgs.kdePackages.qtvirtualkeyboard

    # From flake inputs
    inputs.bzmenu.packages.${stdenv.hostPlatform.system}.default
    inputs.yt-x.packages.${stdenv.hostPlatform.system}.default
    inputs.zen-browser.packages.${stdenv.hostPlatform.system}.default

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
        # Applicationws
        qbittorrent
        telegram-desktop
        zoom-us
        google-chrome
        protonup-qt
        steam
        tor-browser
        localsend


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
        tldr
        yt-dlg
        yt-dlp

        # Creative
        krita
        vlc
        gimp
      ];
    })
  ];
}
