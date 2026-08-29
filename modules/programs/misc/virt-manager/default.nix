{pkgs, ...}: {
  programs.virt-manager.enable = true;

  environment.systemPackages = with pkgs; [
    virt-viewer
    spice
    spice-gtk
    spice-protocol
    virtio-win
    win-spice
  ];

  virtualisation = {
    libvirtd = {
      enable = true;
      # Enabling networking.nftables would otherwise switch libvirt to its
      # nftables backend. Keep the previously working iptables-nft path until
      # VM networking is explicitly runtime-tested on this host.
      firewallBackend = "iptables";
    };
    spiceUSBRedirection.enable = true;
  };
}
