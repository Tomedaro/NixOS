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
  home-manager.sharedModules = [
    (_: {
      home.packages = with pkgs; [
        (inputs.nixvim.packages.${stdenv.hostPlatform.system}.full.extend {
          opts = {
            relativenumber = pkgs.lib.mkForce false;
          };

          plugins = {
            hardtime.enable = pkgs.lib.mkForce false;
            snacks.enable = true;
          };

          extraPlugins = [
            (pkgs.vimUtils.buildVimPlugin {
              pname = "vim-coach.nvim";
              version = "unstable";

              src = pkgs.fetchFromGitHub {
                owner = "shahshlok";
                repo = "vim-coach.nvim";
                rev = "master";
                hash = "sha256-gXrTWq8pA7T2h4fSpx1F5fFVKbCSQ0VD1fK24q/tMIc=";
              };

              dependencies = with pkgs.vimPlugins; [
                snacks-nvim
              ];
            })
          ];

          extraConfigLua = ''
            require("vim-coach").setup()
          '';
        })
      ];

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
          terminal = false;
        };
      };
    })
  ];
}
