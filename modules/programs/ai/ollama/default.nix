{ config, pkgs, lib, ... }:
{
  services.ollama = {
    enable = true;
    package = pkgs.ollama-cpu;        # CPU-only: no NVIDIA/AMD GPU on your machine

    # Preload model at service start — avoids cold-start delay when pipe fires
    loadModels = [ "qwen3.5:4b" ];

    environmentVariables = {
      OLLAMA_MAX_LOADED_MODELS = "1"; # only keep one model in RAM at a time
      OLLAMA_KEEP_ALIVE = "10m";      # unload after 10 min idle, free up ~4GB
    };
  };
}
