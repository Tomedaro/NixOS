{ lib, stdenv, fetchurl, autoPatchelfHook, libgcc }:

stdenv.mkDerivation rec {
  pname = "lean-ctx";
  version = "3.7.5";
  target = stdenv.hostPlatform.linuxArch + "-unknown-linux-gnu";

  src = fetchurl {
    url = "https://github.com/yvgude/lean-ctx/releases/download/v${version}/lean-ctx-${target}.tar.gz";
    hash = "sha256-xYav5kEUFCuuNgtcJ/NhjS++T4K6Sz4GQglvM7Jo5NM=";
  };

  nativeBuildInputs = [ autoPatchelfHook ];
  sourceRoot = ".";
  buildInputs = [ libgcc ];

  installPhase = ''
    install -Dm755 lean-ctx $out/bin/lean-ctx
  '';

  meta = {
    description = "Context OS for AI coding agents — compresses, remembers, routes, and verifies tokens";
    homepage = "https://leanctx.com";
    license = lib.licenses.asl20;
    platforms = lib.platforms.linux;
    mainProgram = "lean-ctx";
  };
}
