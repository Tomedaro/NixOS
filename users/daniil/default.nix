{
  _class = "homeManager";

  imports = [
    ../../modules/programs/cli/starship
    ../../modules/programs/cli/tmux
    ../../modules/programs/cli/lazygit
    ../../modules/programs/cli/cava
  ];

  # Reusable personal Home Manager baseline. Installation-specific compatibility
  # state (home.stateVersion) belongs to the concrete user@host integration.
  programs.home-manager.enable = true;
  xdg.enable = true;
}
