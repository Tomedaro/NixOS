{ pkgs, inputs ? {}, paths }:

let
  system = pkgs.stdenv.hostPlatform.system;

  piPackage =
    if inputs ? piNix
    then inputs.piNix.packages.${system}.coding-agent
    else pkgs.pi-coding-agent;

  piNpm = pkgs.writeShellScriptBin "pi-npm" ''
    set -euo pipefail
    mkdir -p "${paths.piNpmDir}"
    export NPM_CONFIG_PREFIX="${paths.piNpmDir}"
    exec ${pkgs.nodejs_latest}/bin/npm "$@"
  '';

  piRuntimePath = pkgs.lib.makeBinPath (
    [
      piNpm
      pkgs.nodejs_latest
      pkgs.git
      pkgs.openssh
      pkgs.ripgrep
      pkgs.fd
      pkgs.jq
      pkgs.curl
      pkgs.gnutar
      pkgs.unzip
      pkgs.nix
      pkgs.coreutils
      pkgs.gnused
      pkgs.gnugrep
      pkgs.gawk
      pkgs.findutils
      pkgs.util-linux
    ]
    ++ pkgs.lib.optional (pkgs ? bubblewrap) pkgs.bubblewrap
  );

  piWrapped = pkgs.symlinkJoin {
    name = "pi-coding-agent";
    paths = [ piPackage ];
    buildInputs = [ pkgs.makeWrapper ];

    postBuild = ''
      wrapProgram $out/bin/pi \
        --prefix PATH : ${piRuntimePath}:${paths.piNpmBin} \
        --set NPM_CONFIG_PREFIX ${paths.piNpmDir} \
        --set PI_SKIP_VERSION_CHECK 1 \
        --set PI_TELEMETRY 0 \
        --set PI_CACHE_RETENTION long
    '';
  };
in
{
  inherit piWrapped piNpm piPackage piRuntimePath;
}
