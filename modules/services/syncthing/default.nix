# ../../modules/services/syncthing.nix
{ pkgs, config, lib, ... }:

let
  # Replace 'your_gui_username' with your desired Syncthing Web UI username
  guiUser = "daniil"; # Or your preferred username

  # IMPORTANT: Generate your password hash!
  # In your terminal, run: syncthing generate --password="your_secret_password_here"
  # Then replace the example hash below with the output from that command.
  # Make sure `syncthing` is available in your PATH when you run this,
  # e.g., by temporarily adding it with `nix-shell -p syncthing`.
  guiPasswordHash = "$2a$10$yourGeneratedBcryptHashHere"; # <- REPLACE THIS

in
{
  # This module will be imported into home-manager's configuration.
  # So, we define home-manager options here.

  # Ensure the Syncthing package is available
  home.packages = with pkgs; [ 
    syncthing
  ];

  # Enable and configure the Syncthing user service
  services.syncthing = {
    enable = true;
    # Default directories are usually fine:
    # dataDir = "${config.home.homeDirectory}/.local/share/syncthing";
    # configDir = "${config.home.homeDirectory}/.config/syncthing";

    # Declaratively configure GUI authentication for security
    # This is optional; you can also set this via the Web UI initially.
    # If you set it here, it will be enforced by your Nix configuration.
    # settings = {
    # gui = {
    # user = guiUser;
    # password = guiPasswordHash; # Uses the hash defined above
    # useTLS = false; # Set to true if you plan to expose it via HTTPS, default for localhost is false
        # address = "127.0.0.1:8384"; # Default listen address, usually fine.
    # };
      # You can add other global Syncthing settings here if needed.
      # For example, to set a device name declaratively:
      # device = {
      #   name = "NixOS-Laptop"; # Or your desired device name
      # };
      # However, device name and folder sharing are often easier to manage via the UI initially.
    # };
  };

  # If you want to open the firewall for Syncthing (if you have a strict firewall enabled)
  # This is usually for allowing incoming connections from other devices on your LAN/WAN.
  # For local discovery and relaying, this might not always be necessary, but good to be aware of.
  # networking.firewall.allowedTCPPorts = [ 22000 ]; # Syncthing's main listening port
  # networking.firewall.allowedUDPPorts = [ 21027 ]; # For local discovery
  # Note: Firewall settings belong in your main NixOS configuration (`configuration.nix`),
  # not directly in a home-manager module if it's managing the system firewall.
  # You could expose an option from this module if you want to control it centrally.
}
