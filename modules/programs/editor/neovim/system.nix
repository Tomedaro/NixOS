{pkgs, ...}: {
  environment.systemPackages = with pkgs; [
    gcc # to compile treesitter parsers
    nodejs
    nil
    nixfmt-tree
    ripgrep
  ];
}
