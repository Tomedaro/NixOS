{
  spicetifyModule,
  spicetifyPackages,
  thunderbirdTheme,
}: {
  _class = "homeManager";

  imports = [
    ./packages.nix
    ../../modules/programs/media/discord
    ../../modules/programs/cli/starship
    ../../modules/programs/cli/tmux
    ../../modules/programs/cli/lazygit
    ../../modules/programs/cli/cava
    ../../modules/programs/cli/direnv
    ../../modules/programs/cli/btop
    ../../modules/programs/media/obs-studio
    ../../modules/programs/media/mpv
    (import ../../modules/programs/media/spicetify {
      inherit spicetifyModule spicetifyPackages;
    })
    (import ../../modules/programs/media/thunderbird {
      inherit thunderbirdTheme;
    })
  ];

  # Reusable personal Home Manager baseline. Installation-specific compatibility
  # state (home.stateVersion) belongs to the concrete user@host integration.
  programs.home-manager.enable = true;
  xdg.enable = true;
}
