{ config, pkgs, lib, ... }:
{
  environment.systemPackages = with pkgs; [
    nodejs_22
    ffmpeg
    tesseract
    libnotify
    curl
  ];

  # Ensure /bin/sh exists (screenpipe's npm package spawns "sh" by name)
  environment.binsh = "${pkgs.bash}/bin/bash";

  xdg.portal = {
    enable = true;
    extraPortals = [ pkgs.xdg-desktop-portal-wlr ];
  };

  systemd.user.services.screenpipe = {
    description = "Screenpipe — local screen recorder and AI agent runtime";
    after    = [ "graphical-session.target" ];
    wants    = [ "graphical-session.target" ];
    wantedBy = [ "graphical-session.target" ];

    # This is the correct NixOS way to give a service PATH.
    # It prepends all these packages' bin/ dirs before the service starts.
    path = with pkgs; [
      bash
      coreutils
      nodejs_22
      ffmpeg
      tesseract
      libnotify
      curl
    ];

    serviceConfig = {
      ExecStart        = "${pkgs.nodejs_22}/bin/npx --yes screenpipe@latest record";
      Restart          = "on-failure";
      RestartSec       = "15s";
      WorkingDirectory = "%h";
      PassEnvironment  = [
        "WAYLAND_DISPLAY"
        "DISPLAY"
        "XDG_RUNTIME_DIR"
        "DBUS_SESSION_BUS_ADDRESS"
      ];
    };

    environment = {
      OPENAI_API_KEY  = "ollama";
      OPENAI_BASE_URL = "http://localhost:11434/v1";
    };
  };
}
