{
  inputs,
  lib,
  pkgs,
  ...
}:
let
  system = pkgs.stdenv.hostPlatform.system;
  ompPackage = inputs.llm-agents.packages.${system}.omp;
in
{
  environment.systemPackages = [
    ompPackage

    # Useful for OMP plugin installs and custom tools.
    pkgs.bun
    pkgs.git
    pkgs.ripgrep
    pkgs.fd
    pkgs.jq
  ];

  home-manager.sharedModules = [
    (_: {
      home.file.".omp/agent/config.yml".source = ./omp-config.yml;
      home.file.".omp/agent/skills".source = ./omp-skills;
      home.file.".omp/agent/tools".source = ./omp-tools;

      programs.zsh.shellAliases.o = lib.mkDefault "omp";
      programs.bash.shellAliases.o = lib.mkDefault "omp";
    })
  ];
}
