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
    # Remaining host-side tools and integrations; see home-manager-ownership.md.
    easyeffects
    anki-wayland-fixed
    captive-browser
    bleachbit
    android-tools
    woeusb
    sedutil

    # Coupled development and browser integration
    lean-ctx
    firefoxpwa
    (inputs.zen-browser.packages.${stdenv.hostPlatform.system}.beta.override {
      nativeMessagingHosts = [pkgs.firefoxpwa];
    })
  ];
}
