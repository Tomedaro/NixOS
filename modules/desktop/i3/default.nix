{
  browser,
  terminal,
  wallpaper,
}: {
  lib,
  pkgs,
  ...
}: let
  inherit (lib) getExe getExe';
  defaultWallpaper = wallpaper;
  monitors = pkgs.callPackage ./scripts/monitors.nix {};
  wallpaperScript = pkgs.callPackage ./scripts/wallpaper.nix {};
in {
  imports = [
    ../../themes/Catppuccin
    (import ../hyprland/programs/rofi {inherit terminal;})
    ./polybar
    (import ./dunst.nix {inherit browser;})
    ./picom.nix
  ];

  _class = "homeManager";
  xsession.windowManager.i3 = {
    enable = true;
    package = pkgs.i3;
    config = {
      floating.criteria = [{class = "^Mpv$";}];
      gaps.smartBorders = "on";
      window.titlebar = false;
      window.hideEdgeBorders = "both";
      gaps = {
        inner = 4;
        outer = 4;
      };
      colors = {
        focused = {
          border = "#A4B9EF";
          background = "#A4B9EF";
          text = "#A4B9EF";
          indicator = "#A4B9EF";
          childBorder = "#A4B9EF";
        };
        unfocused = {
          border = "#1F1F31";
          background = "#1F1F31";
          text = "#1F1F31";
          indicator = "#1F1F31";
          childBorder = "#1F1F31";
        };
        focusedInactive = {
          border = "#1F1F31";
          background = "#1F1F31";
          text = "#1F1F31";
          indicator = "#1F1F31";
          childBorder = "#1F1F31";
        };
      };
      keybindings = import ./keybindings.nix {
        inherit pkgs terminal browser;
      };
      bars = [];
      startup = [
        {
          command = "${getExe monitors}";
          always = true;
          notification = false;
        }
        {
          command = "systemctl --user restart picom";
          always = true;
          notification = false;
        }
        {
          command = "sleep 1.5 && polybar &";
          always = true;
          notification = false;
        }
        {
          command = "${getExe wallpaperScript} ${../../themes/wallpapers/${defaultWallpaper}}";
          always = false;
          notification = false;
        }
        {
          command = "dunst";
          always = false;
          notification = false;
        }
      ];
      # defaultWorkspace = "workspace number 1";
      workspaceOutputAssign = [
        {
          workspace = "1";
          output = "DP-0";
        }
        {
          workspace = "2";
          output = "DP-0";
        }
        {
          workspace = "3";
          output = "DP-0";
        }
        {
          workspace = "4";
          output = "DP-0";
        }
        {
          workspace = "5";
          output = "HDMI-0";
        }
        {
          workspace = "6";
          output = "HDMI-0";
        }
        {
          workspace = "7";
          output = "HDMI-0";
        }
        {
          workspace = "8";
          output = "HDMI-1";
        }
        {
          workspace = "9";
          output = "HDMI-1";
        }
        {
          workspace = "10";
          output = "DP-0";
        }
      ];
      assigns = {
        # "1" = [
        #   {class = "^kitty$";}
        #   {class = "^Alacritty$";}
        #   {class = "^org.wezfurlong.wezterm$";}
        # ];
        # "2" = [
        #   {class = "^code$";}
        #   {class = "^VSCodium$";}
        #   {class = "^code-url-handler$";}
        #   {class = "^codium-url-handler$";}
        # ];
        # "3" = [
        #   {class = "^krita$";}
        #   {title = ".*Godot.*$";}
        #   {title = "GNU Image Manipulation Program.*$";}
        #   {class = "^factorio$";}
        #   {class = "^steam$";}
        # ];
        # "Web" = [
        #   # Hyprland used workspace 5
        #   {class = "^firefox$";}
        #   {class = "^floorp$";}
        #   {class = "^zen$";}
        # ];
        # "Music" = [
        #   {class = "^Spotify$";}
        #   {title = ".*Spotify.*$";}
        # ];
      };
    };
  };
}
