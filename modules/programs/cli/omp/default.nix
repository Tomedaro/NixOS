{ inputs, pkgs, ... }:

let
  system = pkgs.stdenv.hostPlatform.system;
in
{
  environment.systemPackages = [
    inputs.llm-agents.packages.${system}.omp

    # Useful for OMP plugin installs and custom tools.
    pkgs.bun
    pkgs.git
    pkgs.ripgrep
    pkgs.fd
    pkgs.jq
  ];
}
