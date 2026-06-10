{ inputs ? {} }:
{ config, pkgs, lib, ... }:

let
  paths = import ./lib/paths.nix { inherit config; };
  package = import ./package.nix { inherit pkgs inputs paths; };
  scripts = import ./scripts.nix {
    inherit pkgs lib paths;
    inherit (package) piWrapped piNpm;
  };
  wrappers = import ./wrappers.nix {
    inherit pkgs lib paths scripts;
    inherit (package) piWrapped piNpm;
  };
in
{
  home.packages = [
    package.piNpm
    scripts.piBootstrap
    scripts.piStudyInit
    scripts.piStudyTutorInit
    scripts.piWorkInit
    scripts.piDoctor
    scripts.piDriftCheck
    scripts.piCompatCheck
    scripts.piSourceCheck
    scripts.ankiSafeWriter
    scripts.piTestAnkiSafeWriter
    wrappers.piSmart
    wrappers.piRaw
    wrappers.piAdmin
    wrappers.piReadonly
    wrappers.piCautious
    wrappers.piSafe
    wrappers.piNixos
    wrappers.piStudy
    wrappers.piStudyTutor
    wrappers.piWork
    wrappers.piResearch
    wrappers.piTrusted
  ];

  home.sessionPath = [
    paths.piNpmBin
  ];
}
