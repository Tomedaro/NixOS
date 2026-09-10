{pkgs, ...}: {
  # Optional dependencies
  # https://hyprpanel.com/getting_started/astal.html#dependencies
  environment.systemPackages = with pkgs; [
    wl-clipboard
    python314Packages.gpustat
    brightnessctl
    wf-recorder
  ];
}
