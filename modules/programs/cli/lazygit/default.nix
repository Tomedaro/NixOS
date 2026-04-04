<<<<<<< HEAD
{pkgs, ...}: let
  fromYAML = f: let
    jsonFile =
      pkgs.runCommand "lazygit yaml to attribute set" {nativeBuildInputs = [pkgs.jc];} # bash
      
      ''
        jc --yaml < "${f}" > "$out"
      '';
  in
    builtins.elemAt (builtins.fromJSON (builtins.readFile jsonFile)) 0;
in {
=======
{ pkgs, ... }:
let
  fromYAML =
    f:
    let
      jsonFile =
        pkgs.runCommand "lazygit yaml to attribute set" { nativeBuildInputs = [ pkgs.jc ]; } # bash

          ''
            jc --yaml < "${f}" > "$out"
          '';
    in
    builtins.elemAt (builtins.fromJSON (builtins.readFile jsonFile)) 0;
in
{
>>>>>>> upstream/master
  home-manager.sharedModules = [
    (_: {
      home.shellAliases = {
        lg = "lazygit";
      };
      programs.lazygit = {
        enable = true;
        settings = {
<<<<<<< HEAD
          gui = fromYAML (pkgs.fetchFromGitHub {
=======
          gui = fromYAML (
            pkgs.fetchFromGitHub {
>>>>>>> upstream/master
              owner = "catppuccin";
              repo = "lazygit";
              rev = "d3c95a67ea3f778f7705d8ef814f87ac5213436d";
              sha256 = "01vhir6243k9wfvlgadv7wsc2s9yb92l67piqsl1dm6kwlhshr3g";
            }
<<<<<<< HEAD
            + "/themes/mocha/blue.yml");
=======
            + "/themes/mocha/blue.yml"
          );
>>>>>>> upstream/master
          # gui = fromYAML (
          #   pkgs.catppuccin + "/lazygit/themes/blue.yml"
          # );
          git = {
            overrideGpg = true;
          };
        };
      };
    })
  ];
}
