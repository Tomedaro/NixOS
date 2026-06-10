{ pkgs, inputs, ... }:

let
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
    freetube
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
    sddm-astronaut        # Overlaid
    kdePackages.qtsvg
    kdePackages.qtmultimedia
    kdePackages.qtvirtualkeyboard

    # From flake inputs
    inputs.bzmenu.packages.${stdenv.hostPlatform.system}.default
    inputs.yt-x.packages.${stdenv.hostPlatform.system}.default
    inputs.zen-browser.packages.${stdenv.hostPlatform.system}.default

    # Dev tools
    lean-ctx
    obsidian
    ludusavi
    proton-vpn
    github-desktop
  ];

  # Personal home packages via home-manager
  home-manager.sharedModules = [
    (_: {
      home.packages = with pkgs; [
        # Applications
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
