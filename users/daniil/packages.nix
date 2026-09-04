{pkgs, ...}: {
  _class = "homeManager";

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

    # Personal applications, also available outside the selected desktop.
    freetube
    qimgv
    feh
    feh.doc # Preserve the documentation output previously installed by NixOS.
    foliate
    sioyek
    guvcview
    obsidian
    ludusavi
    github-desktop
  ];
}
