{
  pkgs,
  lib,
  host,
  config,
  ...
}:
let
  inherit (import ../../hosts/${host}/variables.nix) terminal;
in
let
  scriptArgs = {
    inherit host pkgs lib config terminal;
  };

  scripts = [
    (import ./rebuild.nix scriptArgs)
    (import ./rollback.nix scriptArgs)
    (import ./launcher.nix scriptArgs)
    (import ./network.nix scriptArgs)
    (import ./tmux-sessionizer.nix scriptArgs)
    (import ./extract.nix scriptArgs)
    (import ./driverinfo.nix scriptArgs)
    (import ./underwatt.nix scriptArgs)
  ];
in
{
  environment.systemPackages = scripts;
}
