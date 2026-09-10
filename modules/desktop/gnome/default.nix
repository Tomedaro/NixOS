{
  kbdLayout,
  wallpaper,
}: {...}: {
  _class = "homeManager";

  imports = [
    (import ./dconf.nix {inherit kbdLayout wallpaper;})
    ../../themes/Catppuccin
  ];
}
