{ inputs ? {}, ... }:

{
  home-manager.sharedModules = [
    (import ./home-module.nix { inherit inputs; })
  ];
}
