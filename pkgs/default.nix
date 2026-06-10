{ host, pkgs, ... }:
{
  # these are overlaid into nixpkgs automatically.
  # for example: environment.systemPackages = with pkgs; [pokego];
  pokego = pkgs.callPackage ./pokego.nix { };
  lean-ctx = pkgs.callPackage ./lean-ctx.nix { };
}
