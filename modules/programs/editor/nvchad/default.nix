{nvchadModule}: {pkgs, ...}: {
  _class = "homeManager";
  imports = [nvchadModule];
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
        ps:
          with ps; [
            python-lsp-server
            flake8
          ]
      ))
    ];
    hm-activation = true;
    backup = false;
  };
}
