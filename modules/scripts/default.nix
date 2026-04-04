{
  pkgs,
  lib,
<<<<<<< HEAD
  ...
}: let
  # Recursively find all .nix files, excluding default.nix only at the top level
  findNixFiles = isTopLevel: path: let
    entries = builtins.readDir path;
    files =
      if isTopLevel
      then lib.filterAttrs (name: type: type == "regular" && lib.hasSuffix ".nix" name && name != "default.nix") entries
      else lib.filterAttrs (name: type: type == "regular" && lib.hasSuffix ".nix" name) entries;
    filePaths = map (name: path + "/${name}") (lib.attrNames files);
    # Find subdirectories to recurse into
    dirs = lib.filterAttrs (_name: type: type == "directory") entries;
    subDirPaths = map (name: path + "/${name}") (lib.attrNames dirs);
    subFiles = lib.concatMap (findNixFiles false) subDirPaths;
  in
    filePaths ++ subFiles;

  nixFiles = findNixFiles true ./.;

  # Convert each .nix file into a derivation, with validation
  # scriptDerivations = builtins.filter lib.isDerivation (map (file: pkgs.callPackage file {}) nixFiles);
  scriptDerivations =
    map (
      file: let
        drv = pkgs.callPackage file {};
      in
        if lib.isDerivation drv
        then drv
        else throw "Script from ${toString file} is not a derivation, got: ${builtins.toString drv}"
    )
    nixFiles;
in {
  environment.systemPackages = scriptDerivations;
=======
  host,
  config,
  ...
}:
let
  inherit (import ../../hosts/${host}/variables.nix) terminal;
in
let
  # Define your custom args once
  scriptArgs = {
    inherit
      host
      pkgs
      lib
      config
      terminal
      ;
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
    # Add new scripts here as you create them
  ];
in
{
  environment.systemPackages = scripts;
>>>>>>> upstream/master
}
