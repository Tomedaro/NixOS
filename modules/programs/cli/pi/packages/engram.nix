{ pkgs, lib }:
pkgs.buildGoModule rec {
  pname = "engram";
  version = "1.16.1";
  src = pkgs.fetchFromGitHub {
    owner = "Gentleman-Programming";
    repo = "engram";
    rev = "v${version}";
    hash = "sha256-q5X6W/6qkD0zisM1yo6MpU3PgbotRhygLsi/pc2ZeuE=";
  };
  vendorHash = "sha256-O+pC4x4DKNUWr7Sx9iZOjK6a64wrQA4/lnjvkNLBX64=";
  subPackages = [ "cmd/engram" ];
  doCheck = false;
  meta = with lib; {
    description = "Persistent memory system for AI coding agents";
    homepage = "https://github.com/Gentleman-Programming/engram";
    license = licenses.mit;
    mainProgram = "engram";
  };
}
