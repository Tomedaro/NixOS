{
  inputs,
  pkgs,
  ...
}:
{
  home-manager.sharedModules = [
    (_: {
      imports = [ inputs.nvchad4nix.homeManagerModule ];
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
          (python3.withPackages (
            ps: with ps; [
              python-lsp-server
              flake8
            ]
          ))
        ];
        hm-activation = true;
        backup = false;
      };
    })
  ];
}
