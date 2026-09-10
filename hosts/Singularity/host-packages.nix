{
  pkgs,
  inputs,
  ...
}: {
  environment.systemPackages = with pkgs; [
    # Remaining host-side tools and integrations; see home-manager-ownership.md.
    easyeffects
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
