# ~/NixOS/modules/programs/anki/sync-server.nix
{ config, pkgs, lib, ... }:

{
  # Install the dedicated server package
  environment.systemPackages = [ pkgs.anki-sync-server ];

  # Add the necessary firewall port (merges with other definitions)
  networking.firewall.allowedTCPPorts = [ 27701 ];

  # Define the systemd service
  systemd.services.anki-sync-server = {
    description = "Anki Sync Server";
    after = [ "network.target" ];
    wantedBy = [ "multi-user.target" ];
    serviceConfig = {
      Environment = [
        "SYNC_USER1=Daniil:anki2024"    # Consider secrets management later!
        "MAX_SYNC_PAYLOAD_MEGS=1000000"     # Sensible default (100MB)
        "SYNC_PORT=27701"
        "SYNC_HOSTS=0.0.0.0"            # Listen on all interfaces
        # "ANKI_BASE=/path/to/your/Anki2/data/directory" # Optional
      ];
      User = "daniil";
      Group = "users";
      ExecStart = "${pkgs.anki-sync-server}/bin/anki-sync-server";
      Restart = "on-failure";
    };
  };
}
