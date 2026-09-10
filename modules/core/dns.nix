{...}: {
  # DNS is owned by the active NetworkManager connection. DHCP-provided DNS
  # is used directly; no global local resolver or hard-coded upstream is forced.
  services.resolved.enable = false;
  services.unbound.enable = false;
  services.adguardhome.enable = false;
}
