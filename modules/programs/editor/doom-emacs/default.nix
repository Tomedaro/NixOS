{
  doomConfig,
  doomEmacsModule,
}: {pkgs, ...}: {
  _class = "homeManager";

  imports = [doomEmacsModule];

  services.emacs.enable = true;

  programs.doom-emacs = {
    enable = true;
    doomDir = doomConfig;
  };

  home.packages = with pkgs; [nil nixfmt]; # Nix Stuff
}
