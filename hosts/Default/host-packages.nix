{
  pkgs,
  inputs,
  ...
}: let
  anki-wayland-fixed = pkgs.symlinkJoin {
    name = "anki";
    paths = [pkgs.anki-bin];
    buildInputs = [pkgs.makeWrapper];
    postBuild = ''
      wrapProgram $out/bin/anki \
        --set QTWEBENGINE_CHROMIUM_FLAGS "--no-sandbox"
    '';
  };
in {
  environment.systemPackages = with pkgs; [
    # Personal tools
    easyeffects
    freetube
    anki-wayland-fixed
    captive-browser
    bleachbit
    qimgv
    android-tools
    feh
    foliate
    sioyek
    woeusb
    guvcview
    sedutil

    # From flake inputs
    inputs.bzmenu.packages.${stdenv.hostPlatform.system}.default
    inputs.yt-x.packages.${stdenv.hostPlatform.system}.default

    # Dev tools
    lean-ctx
    obsidian
    ludusavi
    github-desktop
    firefoxpwa
    (inputs.zen-browser.packages.${stdenv.hostPlatform.system}.beta.override {
      nativeMessagingHosts = [pkgs.firefoxpwa];
    })
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
        tor-browser
        localsend
        onlyoffice-desktopeditors
        libreoffice-qt-fresh
        signal-desktop

        # Terminal tools
        fuzzel
        cool-retro-term
        htop
        yt-dlg
        yt-dlp

        # Creative
        krita
        vlc
        gimp

        # Dev tooling (linters, formatters, LSPs)
        nixd
        nixfmt
        statix
        deadnix
        ruff
        pyright
        python3
        python3Packages.pytest
        lua-language-server
        stylua
        luajit
        lua51Packages.luacheck
      ];
    })
  ];
}
