{ pkgs, lib, ... }:

let
  ankiSafeWriter = pkgs.writeShellScriptBin "anki-safe-writer" ''
    export ANKI_SAFE_WRITER_STATE="''${ANKI_SAFE_WRITER_STATE:-$HOME/.local/state/anki-safe-writer}"
    exec ${pkgs.python3}/bin/python3 ${./anki_safe_writer.py} "$@"
  '';
in
{
  inherit ankiSafeWriter;
}
