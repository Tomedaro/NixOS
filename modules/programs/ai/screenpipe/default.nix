{ config, pkgs, lib, ... }:
{
  # --- System dependencies ---
  environment.systemPackages = with pkgs; [
    nodejs_22     # required for npx screenpipe@latest
    ffmpeg        # video frame processing
    tesseract     # OCR fallback when accessibility tree isn't available
    libnotify     # notify-send (used by screenpipe's notification endpoint)
    curl          # used inside pipes for API calls
  ];

  # --- Wayland screen capture portal ---
  # Change to xdg-desktop-portal-gnome or -kde if you use GNOME/KDE
  xdg.portal = {
    enable = true;
    extraPortals = [ pkgs.xdg-desktop-portal-wlr ];
  };

  # --- Systemd user service (starts at login for all users) ---
  # screenpipe needs display access, so it runs as a user service
  systemd.user.services.screenpipe = {
    description = "Screenpipe — local screen recorder and AI agent runtime";

    # Wait for the graphical session (Wayland/X11) to be ready
    after    = [ "graphical-session.target" ];
    wants    = [ "graphical-session.target" ];
    wantedBy = [ "graphical-session.target" ];

    serviceConfig = {
      # npx downloads screenpipe on first run, then uses cached version
      ExecStart = "${pkgs.nodejs_22}/bin/npx --yes screenpipe@latest record";
      Restart    = "on-failure";
      RestartSec = "10s";

      # Store data under XDG_DATA_HOME or fall back to ~/.screenpipe
      WorkingDirectory = "%h";
    };

    # Bridge Ollama into the pipe agent (pi) via OpenAI-compatible API.
    # Ollama ignores the key value — any non-empty string works.
    environment = {
      OPENAI_API_KEY  = "ollama";
      OPENAI_BASE_URL = "http://localhost:11434/v1";
    };
  };
}
