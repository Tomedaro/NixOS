{ config }:

let
  home = config.home.homeDirectory;
in
{
  inherit home;

  piAgentDir = "${home}/.pi/agent";
  piNpmDir = "${home}/.pi/agent/npm";
  piNpmBin = "${home}/.pi/agent/npm/bin";
  piSessionsDir = "${home}/.pi/agent/sessions";
  piPoliciesDir = "${home}/.pi/agent/policies";

  learningDir = "${home}/Learning";
  workDir = "${home}/Work";
  nixosRepo = "${home}/NixOS";
  piSourceDir = "${home}/NixOS/modules/programs/cli/pi";
}
