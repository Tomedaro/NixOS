{config, ...}: let
  username = config.workstation.user.name;
in {
  services.syncthing = {
    enable = true;
    # Firewall exposure is restricted to the firewalld home zone. Keep relay
    # and global-discovery behavior at Syncthing defaults.
    openDefaultPorts = false;
    user = "${username}";
    dataDir = "/home/${username}";
    configDir = "/home/${username}/.config/syncthing";
  };
}
