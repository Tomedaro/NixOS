{ lib, pkgs, ... }:

let
  gtkThemeName = "Gruvbox-Orange-Dark-Compact-Medium";

  gruvboxGtk = pkgs.gruvbox-gtk-theme.override {
    colorVariants = [ "dark" ];
    sizeVariants = [ "compact" ];
    themeVariants = [ "orange" ];
    tweakVariants = [ "medium" ];
    iconVariants = [ "Dark" ];
  };

  kvantumThemeName = "Gruvbox-Dark-Brown";

  gruvboxKvantum = pkgs.gruvbox-kvantum.override {
    variant = kvantumThemeName;
  };

  gruvboxIcons = pkgs.gruvbox-plus-icons.override {
    folder-color = "orange";
  };
in
{
  home-manager.sharedModules = [
    (
      { config, ... }:
      {
        home.packages =
          [
            gruvboxGtk
            gruvboxKvantum
            gruvboxIcons

            # Qt5 Kvantum engine
            pkgs.libsForQt5.qtstyleplugin-kvantum
          ]
          ++ lib.optionals
            ((pkgs ? kdePackages) && (pkgs.kdePackages ? qtstyleplugin-kvantum))
            [
              # Qt6 / KDE Frameworks 6 Kvantum engine, if available in your nixpkgs
              pkgs.kdePackages.qtstyleplugin-kvantum
            ];

        qt = {
          enable = true;
          platformTheme.name = "gtk";
          style.name = "kvantum";
        };

        gtk = {
          enable = true;
          gtk2.force = true;

          theme = {
            name = gtkThemeName;
            package = gruvboxGtk;
          };

          iconTheme = {
            package = gruvboxIcons;
            name = "Gruvbox-Plus-Dark";
          };

          gtk3.extraConfig = {
            "gtk-application-prefer-dark-theme" = "1";
          };

          gtk4.extraConfig = {
            "gtk-application-prefer-dark-theme" = "1";
          };
        };

        home.sessionVariables = {
          ADW_COLOR_SCHEME = "prefer-dark";
          GTK_THEME = gtkThemeName;

          # Helps some Qt apps under Hyprland actually pick Kvantum.
          QT_STYLE_OVERRIDE = "kvantum";
        };

        dconf.settings = {
          "org/gnome/desktop/interface" = {
            color-scheme = "prefer-dark";
            gtk-theme = gtkThemeName;
            icon-theme = "Gruvbox-Plus-Dark";
          };
        };

        home.pointerCursor = {
          gtk.enable = true;
          x11.enable = true;
          package = pkgs.bibata-cursors;
          name = "Bibata-Modern-Classic";
          size = 24;
        };

        xdg.configFile = {
          "gtk-4.0/assets" = {
            force = true;
            source = "${config.gtk.theme.package}/share/themes/${config.gtk.theme.name}/gtk-4.0/assets";
          };

          "gtk-4.0/gtk.css" = {
            force = true;
            source = "${config.gtk.theme.package}/share/themes/${config.gtk.theme.name}/gtk-4.0/gtk.css";
          };

          "gtk-4.0/gtk-dark.css" = {
            force = true;
            source = "${config.gtk.theme.package}/share/themes/${config.gtk.theme.name}/gtk-4.0/gtk-dark.css";
          };

          "Kvantum/${kvantumThemeName}".source =
            "${gruvboxKvantum}/share/Kvantum/${kvantumThemeName}";

          "Kvantum/kvantum.kvconfig".source =
            (pkgs.formats.ini { }).generate "kvantum.kvconfig" {
              General.theme = kvantumThemeName;
            };
        };
      }
    )
  ];
}
