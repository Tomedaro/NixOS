{ config, lib, pkgs, ... }:
let
  cfg = config.my.ai.ollama;
in
{
  options.my.ai.ollama = {
    enable = lib.mkEnableOption "local Ollama service";
    package = lib.mkOption {
      type = lib.types.package;
      default = pkgs.ollama-cpu;
      description = "Ollama package to use";
    };
    loadModels = lib.mkOption {
      type = lib.types.listOf lib.types.str;
      default = [ ];
      description = "Models to preload";
    };
  };

  config = lib.mkIf cfg.enable {
    services.ollama = {
      enable = true;
      package = cfg.package;
      loadModels = cfg.loadModels;
    };
  };
}
