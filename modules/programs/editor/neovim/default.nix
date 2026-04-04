<<<<<<< HEAD
{...}: {
  home-manager.sharedModules = [
    (_: {
      programs.neovim.enable = true;
      home.file.".config/nvim" = {
        source = builtins.fetchGit {
          url = "https://github.com/Sly-Harvey/nvim.git";
          rev = "018aad196d833c441ded5b09a8f8e7546d0c1bf1";
        };
        recursive = true;
=======
{
  inputs,
  host,
  pkgs,
  ...
}:
let
  inherit (import ../../../../hosts/${host}/variables.nix) terminal;
in
{
  environment.systemPackages = with pkgs; [
    gcc # to compile treesitter parsers
    nodejs
    nil
    nixfmt-tree
    ripgrep
  ]; # Dependencies
  home-manager.sharedModules = [
    (_: {
      programs.neovim.enable = true;
      xdg.configFile."nvim".source = inputs.neovim;
      xdg.desktopEntries = {
        "nvim" = {
          name = "Neovim wrapper";
          genericName = "Text Editor";
          comment = "Edit text files";
          exec = "${pkgs.${terminal}}/bin/${terminal} --class \"nvim-wrapper\" -e nvim %F";
          icon = "nvim";
          mimeType = [
            "text/plain"
            "text/x-makefile"
          ];
          categories = [
            "Development"
            "TextEditor"
          ];
          terminal = false; # Important: set to false since we're calling kitty directly
        };
>>>>>>> upstream/master
      };
    })
  ];
}
