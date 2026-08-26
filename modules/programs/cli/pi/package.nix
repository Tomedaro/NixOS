{
  pkgs,
  inputs ? {},
  paths,
}: let
  system = pkgs.stdenv.hostPlatform.system;
  nodejs = pkgs.nodejs_24;

  piPackage =
    if inputs ? piNix
    then inputs.piNix.packages.${system}.coding-agent
    else pkgs.pi-coding-agent;

  piNpm = pkgs.writeShellScriptBin "pi-npm" ''
    set -euo pipefail
    mkdir -p "${paths.piNpmDir}"
    export NPM_CONFIG_PREFIX="${paths.piNpmDir}"
    exec ${nodejs}/bin/npm "$@"
  '';

  piRuntimePath = pkgs.lib.makeBinPath (
    [
      piNpm
      nodejs
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
      engramPackage
    ]
    ++ pkgs.lib.optional (pkgs ? bubblewrap) pkgs.bubblewrap
  );

  engramPackage = pkgs.callPackage ./packages/engram.nix {};

  # Build mcp-nixos against this system's nixpkgs instead of using the
  # upstream flake package. The upstream package currently applies its
  # fastmcp3 overlay, which forces fastmcp 3.2.4 onto nixpkgs' split
  # fastmcp/fastmcp-slim packaging and leaves fastmcp-slim with an invalid
  # sourceRoot.
  mcpNixosPackage = inputs.mcp-nixos.lib.mkMcpNixos {inherit pkgs;};

  mcpNixosWrapper = pkgs.writeShellScriptBin "mcp-nixos" ''
    exec ${mcpNixosPackage}/bin/mcp-nixos "$@"
  '';

  mcpEngramArgs = [
    "-e"
    "const { spawn } = require('node:child_process'); const bin = process.env.ENGRAM_BIN || 'engram'; const child = spawn(bin, ['mcp', '--tools=agent'], { stdio: 'inherit' }); child.on('error', () => process.exit(127)); child.on('exit', (code, signal) => { if (typeof code === 'number') process.exit(code); process.kill(process.pid, signal || 'SIGTERM'); });"
  ];
  mcpNixosSrv = {
    command = "${mcpNixosWrapper}/bin/mcp-nixos";
    args = [];
    lifecycle = "lazy";
    directTools = true;
  };
  mcpEngramSrv = {
    command = "node";
    args = mcpEngramArgs;
    lifecycle = "lazy";
    directTools = false;
  };
  mcpJsonFormat = pkgs.formats.json {};
  generatedMcpGlobal = mcpJsonFormat.generate "mcp-global.json" {
    mcpServers = {
      nixos = mcpNixosSrv;
      engram = mcpEngramSrv;
    };
  };
  generatedMcpNixos = mcpJsonFormat.generate "mcp-nixos.json" {
    mcpServers = {
      nixos = mcpNixosSrv;
      engram = mcpEngramSrv;
    };
  };

  piWrapped = pkgs.symlinkJoin {
    name = "pi-coding-agent";
    paths = [piPackage];
    buildInputs = [pkgs.makeWrapper];

    postBuild = ''
      wrapProgram $out/bin/pi \
        --prefix PATH : ${piRuntimePath}:${paths.piNpmBin} \
        --set NPM_CONFIG_PREFIX ${paths.piNpmDir} \
        --set PI_SKIP_VERSION_CHECK 1 \
        --set PI_TELEMETRY 0 \
        --set PI_CACHE_RETENTION long
    '';
  };
in {
  inherit
    piWrapped
    piNpm
    piPackage
    piRuntimePath
    engramPackage
    mcpNixosWrapper
    generatedMcpGlobal
    generatedMcpNixos
    ;
}
