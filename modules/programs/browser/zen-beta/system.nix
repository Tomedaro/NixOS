{
  inputs,
  pkgs,
  ...
}: {
  workstationInternal.browser.systemPackages = [
    pkgs.firefoxpwa
    (inputs.zen-browser.packages.${pkgs.stdenv.hostPlatform.system}.beta.override {
      nativeMessagingHosts = [pkgs.firefoxpwa];
    })
  ];
}
