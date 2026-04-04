{
  inputs,
  pkgs,
  ...
<<<<<<< HEAD
}: {
  home-manager.sharedModules = [
    (_: {
      imports = [inputs.nvchad4nix.homeManagerModule];
=======
}:
{
  home-manager.sharedModules = [
    (_: {
      imports = [ inputs.nvchad4nix.homeManagerModule ];
>>>>>>> upstream/master
      programs.nvchad = {
        enable = true;
        extraPlugins = ''
          return {
            {
              "Sly-Harvey/radium.nvim",
              priority = 1000,
            },
          }
        '';
        extraPackages = with pkgs; [
          nixd
          # nodePackages.bash-language-server
          # docker-compose-language-service
          # dockerfile-language-server-nodejs
          # emmet-language-server
          /*
<<<<<<< HEAD
           (python3.withPackages (ps:
          with ps; [
            python-lsp-server
            flake8
          ]))
=======
             (python3.withPackages (ps:
            with ps; [
              python-lsp-server
              flake8
            ]))
>>>>>>> upstream/master
          */
        ];
        hm-activation = true;
        backup = false;
      };
    })
  ];
}
