{pkgs, ...}: {
  # Optional dependencies
  environment.systemPackages = with pkgs; [
    wl-clipboard
    brightnessctl
    # wf-recorder
  ];
}
