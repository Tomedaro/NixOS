{
  _class = "homeManager";

  programs.direnv = {
    enable = true;
    config.global.warn_timeout = "60s";
    enableBashIntegration = true;
    enableZshIntegration = true;
    enableFishIntegration = false;
    enableNushellIntegration = false;
  };
}
