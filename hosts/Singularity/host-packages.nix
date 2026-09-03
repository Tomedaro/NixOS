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
}
