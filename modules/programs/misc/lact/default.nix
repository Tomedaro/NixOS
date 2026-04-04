{ pkgs, ... }:
let
  lact = pkgs.lact.overrideAttrs (_: { doCheck = false; });
in {
  systemd = {
    packages = [ lact ];
    services.lactd.wantedBy = [ "multi-user.target" ];
  };
  environment.systemPackages = [ lact ];
}
