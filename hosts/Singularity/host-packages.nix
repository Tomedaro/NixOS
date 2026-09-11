{
  config,
  pkgs,
  ...
}: {
  environment.systemPackages =
    (with pkgs; [
      # Remaining host-side tools and integrations; see home-manager-ownership.md.
      easyeffects
      captive-browser
      bleachbit
      android-tools
      woeusb
      sedutil

      # Coupled development integration
      lean-ctx
    ])
    ++ config.workstationInternal.browser.systemPackages;
}
