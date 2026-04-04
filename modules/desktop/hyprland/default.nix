{
  host,
  lib,
  pkgs,
  ...
}:
let
  inherit (lib) getExe getExe';
  inherit (import ../../../hosts/${host}/variables.nix)
    bar
    waybarTheme
    browser
    terminal
    tuiFileManager
    kbdLayout
    kbdVariant
    defaultWallpaper
    ;

  # Script modules
  autoclicker    = pkgs.callPackage ./scripts/autoclicker.nix { };
  batterynotify  = pkgs.callPackage ./scripts/batterynotify.nix { };
  clipmanager    = pkgs.callPackage ./scripts/clipmanager.nix { };
  gamemode       = pkgs.callPackage ./scripts/gamemode.nix { };
  keyboardswitch = pkgs.callPackage ./scripts/keyboardswitch.nix { };
  keybinds-yad   = pkgs.callPackage ./scripts/keybinds-yad.nix { };
  rofimusic      = pkgs.callPackage ./scripts/rofimusic.nix { };
  screen-record  = pkgs.callPackage ./scripts/screen-record.nix { };
  screenshot     = pkgs.callPackage ./scripts/screenshot.nix { };
  wallpaper      = pkgs.callPackage ./scripts/wallpaper.nix { inherit defaultWallpaper; };
  zoom           = pkgs.callPackage ./scripts/zoom.nix { };

  # Personal: per-device keyboard names
  laptopKbdName = "at-translated-set-2-keyboard";
  urchinKbdName = "urchin-keyboard";
in
{
  imports = [
    ../../themes/Catppuccin
    ./programs/wlogout
    ./programs/rofi
    ./programs/hypridle
    ./programs/hyprlock
  ]
  ++ lib.optional  (bar == "hyprpanel") ./programs/hyprpanel
  ++ lib.optionals (bar == "noctalia") [
    ./programs/swaync
    ./programs/noctalia
  ]
  ++ lib.optionals (bar == "waybar") [
    ./programs/swaync
    ./programs/waybar/${waybarTheme}.nix
  ];

  environment.systemPackages = with pkgs; [
    pavucontrol
    swappy
    cliphist
    wl-clipboard
  ];

  systemd.user.services.hyprpolkitagent = {
    description = "Hyprpolkitagent - Polkit authentication agent";
    wantedBy = [ "graphical-session.target" ];
    wants    = [ "graphical-session.target" ];
    after    = [ "graphical-session.target" ];
    serviceConfig = {
      Type          = "simple";
      ExecStart     = "${pkgs.hyprpolkitagent}/libexec/hyprpolkitagent";
      Restart       = "on-failure";
      RestartSec    = 1;
      TimeoutStopSec = 10;
    };
  };

  services.displayManager.defaultSession = "hyprland";

  programs.hyprland = {
    enable  = true;
    package = pkgs.hyprland;
    # withUWSM = true;
  };

  home-manager.sharedModules = [
    (
      { config, ... }:
      {
        xdg.portal = {
          enable           = true;
          extraPortals     = with pkgs; [ xdg-desktop-portal-gtk ];
          xdgOpenUsePortal = true;
          configPackages   = [ config.wayland.windowManager.hyprland.package ];
          config.hyprland  = {
            default = [ "hyprland" "gtk" ];
            "org.freedesktop.impl.portal.OpenURI"     = "gtk";
            "org.freedesktop.impl.portal.FileChooser" = "gtk";
            "org.freedesktop.impl.portal.Print"       = "gtk";
          };
        };

        xdg.configFile."hypr/icons" = {
          source    = ./icons;
          recursive = true;
        };

        services.swww.enable = true;

        wayland.windowManager.hyprland = {
          enable  = true;
          package = pkgs.hyprland;
          plugins = [ ];
          systemd = {
            enable    = true;
            variables = [ "--all" ];
          };

          settings = {
            "$mainMod"     = "SUPER";
            "$term"        = "${getExe pkgs.${terminal}}";
            "$editor"      = "code --disable-gpu";
            "$fileManager" = "$term --class \"tuiFileManager\" -e ${tuiFileManager}";
            "$browser"     = browser;

            env = [
              "XDG_CURRENT_DESKTOP,Hyprland"
              "XDG_SESSION_DESKTOP,Hyprland"
              "XDG_SESSION_TYPE,wayland"
              "GDK_BACKEND,wayland,x11,*"
              "NIXOS_OZONE_WL,1"
              "ELECTRON_OZONE_PLATFORM_HINT,wayland"
              "MOZ_ENABLE_WAYLAND,1"
              "OZONE_PLATFORM,wayland"
              "EGL_PLATFORM,wayland"
              "CLUTTER_BACKEND,wayland"
              "SDL_VIDEODRIVER,wayland"
              "QT_QPA_PLATFORM,wayland;xcb"
              "QT_WAYLAND_DISABLE_WINDOWDECORATION,1"
              "QT_QPA_PLATFORMTHEME,qt6ct"
              "QT_AUTO_SCREEN_SCALE_FACTOR,1"
              "QT_ENABLE_HIGHDPI_SCALING,1"
              "WLR_RENDERER_ALLOW_SOFTWARE,1"
              "NIXPKGS_ALLOW_UNFREE,1"
            ];

            exec-once = [
              "${lib.getExe wallpaper}"
              "${bar}"
              "swaync"
              "nm-applet --indicator"
              "${getExe' pkgs.wl-clipboard "wl-paste"} --type text  --watch cliphist store"
              "${getExe' pkgs.wl-clipboard "wl-paste"} --type image --watch cliphist store"
              "rm '$XDG_CACHE_HOME/cliphist/db'"
              "${getExe batterynotify}"
              "polkit-agent-helper-1"
            ];

            input = {
              # Global default — per-device overrides below
              kb_layout  = "${kbdLayout},ua,us";
              kb_variant = "${kbdVariant},,";
              kb_options = "caps:backspace";
              repeat_delay = 300;
              repeat_rate  = 30;
              follow_mouse = 1;
              sensitivity  = 0.3;
              force_no_accel = false;
              numlock_by_default = true;
              touchpad.natural_scroll = false;
              tablet.output = "current";
            };

            # Personal: per-device keyboard configs
            device = [
              {
                name       = laptopKbdName;
                kb_layout  = "us,ua,us";
                kb_variant = "colemak_dh,,";
              }
              {
                name       = urchinKbdName;
                kb_layout  = "us,ua,us";
                kb_variant = "colemak_dh_ortho,,";
              }
            ];

            general = {
              gaps_in  = 4;
              gaps_out = 9;
              border_size = 2;
              "col.active_border"   = "rgba(ca9ee6ff) rgba(f2d5cfff) 45deg";
              "col.inactive_border" = "rgba(b4befecc) rgba(6c7086cc) 45deg";
              resize_on_border = true;
              layout = "dwindle";
            };

            decoration = {
              shadow.enabled = false;
              rounding    = 10;
              dim_special = 0.3;
              blur = {
                enabled          = true;
                special          = true;
                size             = 6;
                passes           = 2;
                new_optimizations = true;
                ignore_opacity   = true;
                xray             = false;
              };
            };

            group = {
              "col.border_active"        = "rgba(ca9ee6ff) rgba(f2d5cfff) 45deg";
              "col.border_inactive"      = "rgba(b4befecc) rgba(6c7086cc) 45deg";
              "col.border_locked_active" = "rgba(ca9ee6ff) rgba(f2d5cfff) 45deg";
              "col.border_locked_inactive" = "rgba(b4befecc) rgba(6c7086cc) 45deg";
            };

            layerrule = [
              "blur on, match:namespace rofi"
              "ignore_alpha 0.7, match:namespace rofi"
              "blur on, match:namespace ^bar-.*$"
              "blur on, match:namespace notifications-window"
              "blur on, match:namespace mediamenu"
              "blur on, match:namespace notificationsmenu"
              "blur on, match:namespace calendarmenu"
              "blur on, match:namespace audiomenu"
              "blur on, match:namespace networkmenu"
              "blur on, match:namespace energymenu"
              "blur on, match:namespace dashboardmenu"
              "ignore_alpha 0.7, match:namespace ^bar-.*$"
              "ignore_alpha 0.7, match:namespace notifications-window"
              "ignore_alpha 0.7, match:namespace mediamenu"
              "ignore_alpha 0.7, match:namespace notificationsmenu"
              "ignore_alpha 0.7, match:namespace calendarmenu"
              "ignore_alpha 0.7, match:namespace audiomenu"
              "ignore_alpha 0.7, match:namespace networkmenu"
              "ignore_alpha 0.7, match:namespace energymenu"
              "ignore_alpha 0.7, match:namespace dashboardmenu"
              "blur on, match:namespace swaync-control-center"
              "blur on, match:namespace swaync-notification-window"
              "ignore_alpha 0.7, match:namespace swaync-control-center"
              "ignore_alpha 0.8, match:namespace swaync-notification-window"
            ];

            animations = {
              enabled = true;
              bezier = [
                "linear, 0, 0, 1, 1"
                "md3_standard, 0.2, 0, 0, 1"
                "md3_decel, 0.05, 0.7, 0.1, 1"
                "md3_accel, 0.3, 0, 0.8, 0.15"
                "overshot, 0.05, 0.9, 0.1, 1.1"
                "crazyshot, 0.1, 1.5, 0.76, 0.92"
                "hyprnostretch, 0.05, 0.9, 0.1, 1.0"
                "fluent_decel, 0.1, 1, 0, 1"
                "easeInOutCirc, 0.85, 0, 0.15, 1"
                "easeOutCirc, 0, 0.55, 0.45, 1"
                "easeOutExpo, 0.16, 1, 0.3, 1"
              ];
              animation = [
                "windows, 1, 3, md3_decel, popin 60%"
                "border, 1, 10, default"
                "fade, 1, 2.5, md3_decel"
                "workspaces, 1, 3.5, easeOutExpo, slide"
                "specialWorkspace, 1, 3, md3_decel, slidevert"
              ];
            };

            render = {
              direct_scanout = 0;
            };

            ecosystem = {
              no_update_news  = true;
              no_donation_nag = true;
            };

            misc = {
              disable_hyprland_logo    = true;
              mouse_move_focuses_monitor = true;
              swallow_regex            = "^(Alacritty|kitty)$";
              enable_swallow           = true;
              vfr = true;
              vrr = 2; # fullscreen only
            };

            xwayland.force_zero_scaling = false;

            gesture = [
              "3, horizontal, workspace"
              "4, down, close"
              "3, up, fullscreen"
              "3, down, fullscreen"
            ];

            dwindle = {
              pseudotile    = true;
              preserve_split = true;
            };

            master = {
              new_status = "master";
              new_on_top = true;
              mfact      = 0.5;
            };

            windowrule = [
              "tile on, match:title (.*)(Godot)(.*)$"
              "workspace 1, match:class ^(kitty|Alacritty|org.wezfurlong.wezterm)$"
              "workspace 2, match:class ^(code|VSCodium|code-url-handler|codium-url-handler)$"
              "workspace 3, match:class ^(krita|factorio|steam)$"
              "workspace 3, match:title (.*)(Godot)(.*)$"
              "workspace 3, match:title (GNU Image Manipulation Program)(.*)$"
              "workspace 5, match:class ^(firefox|floorp|zen|zen-beta)$"
              "workspace 6, match:class ^(Spotify)$"
              "workspace 6, match:title (.*)(Spotify)(.*)$"

              "opacity 1.00 1.00, match:class ^(firefox|Brave-browser|floorp|zen|zen-beta)$"
              "opacity 0.90 0.80, match:class ^(gcr-prompter)$"
              "opacity 0.90 0.80, match:title ^(Hyprland Polkit Agent)$"
              "opacity 0.90 0.80, match:class ^(discord)$"
              "opacity 0.90 0.80, match:class ^(WebCord)$"
              "opacity 0.80 0.70, match:class ^(kitty|alacritty|Alacritty|org.wezfurlong.wezterm)$"
              "opacity 0.80 0.70, match:class ^(tuiFileManager)$"
              "opacity 0.80 0.70, match:class ^(Steam|steam|steamwebhelper)$"
              "opacity 0.80 0.70, match:class ^(Spotify|spotify)$"
              "opacity 0.80 0.70, match:title ^(Spotify)(.*)$"
              "opacity 0.80 0.70, match:class ^(VSCodium|codium-url-handler)$"
              "opacity 0.80 0.70, match:class ^(code|code-url-handler)$"
              "opacity 0.80 0.70, match:class ^(org.kde.dolphin|org.kde.ark)$"
              "opacity 0.80 0.70, match:class ^(nwg-look|qt5ct|qt6ct)$"
              "opacity 0.80 0.70, match:class ^(yad)$"
              "opacity 0.80 0.70, match:class ^(io.github.ilya_zlobintsev.LACT)$"
              "opacity 0.80 0.70, match:class ^(com.obsproject.Studio)$"
              "opacity 0.80 0.70, match:class ^(gnome-boxes)$"
              "opacity 0.80 0.70, match:class ^(pavucontrol|org.pulseaudio.pavucontrol)$"
              "opacity 0.80 0.70, match:class ^(blueman-manager|.blueman-manager-wrapped)$"
              "opacity 0.80 0.70, match:class ^(nm-applet|nm-connection-editor)$"
              "opacity 0.80 0.70, match:class ^(org.kde.polkit-kde-authentication-agent-1)$"
              "opacity 0.80 0.80, match:class ^(anki-bin)$"

              "float on, match:title ^(Picture-in-Picture)$, match:class ^(zen|zen-beta|floorp|firefox)$"
              "pin on,   match:title ^(Picture-in-Picture)$, match:class ^(zen|zen-beta|floorp|firefox)$"

              "content game, match:tag games"
              "tag +games,   match:class ^(steam_app.*|steam_app_\\d+)$"
              "tag +games,   match:class ^(gamescope)$"
              "sync_fullscreen on, match:tag games"
              "fullscreen on,      match:tag games"
              "border_size 0,      match:tag games"
              "no_shadow on,       match:tag games"
              "no_blur on,         match:tag games"
              "no_anim on,         match:tag games"

              "opacity 0.80 0.70, match:class ^(microfetch)$"
              "float on,           match:class ^(microfetch)$"
              "center on,          match:class ^(microfetch)$"
              "size 802 261,       match:class ^(microfetch)$"

              "float on, match:class ^(qt5ct|nwg-look|org.kde.ark)$"
              "float on, match:class ^(Signal|eog|yad|pavucontrol)$"
              "float on, match:class ^(blueman-manager|.blueman-manager-wrapped)$"
              "float on, match:class ^(nm-applet|nm-connection-editor)$"
              "float on, match:class ^(org.kde.polkit-kde-authentication-agent-1)$"
            ];

            binde = [
              "$mainMod SHIFT, right, resizeactive, 30 0"
              "$mainMod SHIFT, left,  resizeactive, -30 0"
              "$mainMod SHIFT, up,    resizeactive, 0 -30"
              "$mainMod SHIFT, down,  resizeactive, 0 30"
              "$mainMod SHIFT, l, resizeactive, 30 0"
              "$mainMod SHIFT, h, resizeactive, -30 0"
              "$mainMod SHIFT, k, resizeactive, 0 -30"
              "$mainMod SHIFT, j, resizeactive, 0 30"
              ",XF86MonBrightnessDown, exec, ${pkgs.brightnessctl}/bin/brightnessctl set 2%-"
              ",XF86MonBrightnessUp,   exec, ${pkgs.brightnessctl}/bin/brightnessctl set +2%"
              ",XF86AudioLowerVolume,  exec, ${pkgs.pamixer}/bin/pamixer -d 2"
              ",XF86AudioRaiseVolume,  exec, ${pkgs.pamixer}/bin/pamixer -i 2"
            ];

            bind = [
              "$mainMod, question, exec, ${getExe keybinds-yad}"
              "$mainMod, slash,    exec, ${getExe keybinds-yad}"
              "$mainMod CTRL, K,   exec, ${getExe keybinds-yad}"

              "$mainMod, F9,  exec, ${getExe pkgs.hyprsunset} --temperature 3500"
              "$mainMod, F10, exec, pkill hyprsunset"
              "$mainMod, F8,  exec, kill $(cat /tmp/auto-clicker.pid) 2>/dev/null || ${getExe autoclicker} --cps 40"

              # Window/Session
              "$mainMod, Q,      killactive"
              "ALT, F4,          forcekillactive"
              "$mainMod, delete, exit"
              "$mainMod, W,      togglefloating"
              "$mainMod SHIFT, G, togglegroup"
              "ALT, return,      fullscreen"
              "$mainMod ALT, L,  exec, hyprlock"
              "$mainMod, backspace, exec, pkill -x wlogout || wlogout -b 4"
              "$mainMod SHIFT, F,   exec, ${./scripts/windowpin.sh}"  # Personal: window pin
              "$CONTROL, ESCAPE,    exec, pkill waybar || pkill hyprpanel || ${bar}"
              "$mainMod CTRL, mouse_down, exec, ${getExe zoom} in"
              "$mainMod CTRL, mouse_up,   exec, ${getExe zoom} out"

              # Personal: monitor rotation (HDMI-A-1)
              "$mainMod SHIFT, R, exec, hyprctl keyword monitor 'HDMI-A-1,2560x1440@144,1920x0,1,transform,1'"
              "$mainMod SHIFT, T, exec, hyprctl keyword monitor 'HDMI-A-1,2560x1440@144,1920x0,1,transform,0'"

              # Applications
              "$mainMod, Return, exec, $term"
              "$mainMod, T,      exec, $term"
              "$mainMod, E,      exec, $fileManager"
              "$mainMod, C,      exec, $editor"
              "$mainMod, F,      exec, $browser"
              "$mainMod SHIFT, S, exec, spotify"
              "$CONTROL ALT, DELETE, exec, $term -e '${getExe pkgs.btop}'"
              "$CONTROL ALT, M,      exec, $term --class \"microfetch\" --hold -e microfetch"
              "$mainMod CTRL, C,     exec, ${getExe pkgs.hyprpicker} --autocopy --format=hex"

              # Launchers
              "$mainMod, A,      exec, launcher drun"
              "$mainMod, SPACE,  exec, launcher drun"
              "$mainMod, Z,      exec, launcher emoji"
              "$mainMod, G,      exec, launcher games"
              "$mainMod SHIFT, W, exec, launcher wallpaper"
              "$mainMod SHIFT, T, exec, launcher tmux"

              # Personal: per-device keyboard switch
              "$mainMod ALT, K, exec, ${getExe keyboardswitch}"

              "$mainMod SHIFT, N, exec, swaync-client -t -sw"
              "$mainMod SHIFT, Q, exec, swaync-client -t -sw"
              "$mainMod ALT, G,   exec, ${getExe gamemode}"
              "$mainMod, V,       exec, ${getExe clipmanager}"
              "$mainMod, M,       exec, ${getExe rofimusic}"

              # Screenshot/Screen capture
              "$mainMod CTRL, R,  exec, ${getExe screen-record} a"
              "$mainMod ALT, R,   exec, ${getExe screen-record} m"
              "$mainMod, P,       exec, ${getExe screenshot} s"
              "$mainMod CTRL, P,  exec, ${getExe screenshot} sf"
              "$mainMod, print,   exec, ${getExe screenshot} m"
              "$mainMod ALT, P,   exec, ${getExe screenshot} p"

              # Media / System
              ",xf86Sleep,        exec, systemctl suspend"
              ",XF86AudioMicMute, exec, ${pkgs.pamixer}/bin/pamixer --default-source -t"
              ",XF86AudioMute,    exec, ${pkgs.pamixer}/bin/pamixer -t"
              ",XF86AudioPlay,    exec, ${pkgs.playerctl}/bin/playerctl play-pause"
              ",XF86AudioPause,   exec, ${pkgs.playerctl}/bin/playerctl play-pause"
              ",xf86AudioNext,    exec, ${pkgs.playerctl}/bin/playerctl next"
              ",xf86AudioPrev,    exec, ${pkgs.playerctl}/bin/playerctl previous"

              # Focus
              "$mainMod, Tab,   cyclenext"
              "$mainMod, Tab,   bringactivetotop"
              "$mainMod CTRL, right, workspace, r+1"
              "$mainMod CTRL, left,  workspace, r-1"
              "$mainMod CTRL, down,  workspace, empty"
              "$mainMod, left,  movefocus, l"
              "$mainMod, right, movefocus, r"
              "$mainMod, up,    movefocus, u"
              "$mainMod, down,  movefocus, d"
              "ALT, Tab,        movefocus, d"
              "$mainMod, h,     movefocus, l"
              "$mainMod, l,     movefocus, r"
              "$mainMod, k,     movefocus, u"
              "$mainMod, j,     movefocus, d"

              # Scrolling layout columns
              "$mainMod, period, layoutmsg, move +col"
              "$mainMod, comma,  layoutmsg, move -col"

              # Mouse workspace navigation
              "$mainMod, mouse:276, workspace, 5"
              "$mainMod, mouse:275, workspace, 6"
              "$mainMod ALT, mouse:275, workspace, 7"
              "$mainMod SHIFT, mouse:276, movetoworkspace, 5"
              "$mainMod SHIFT, mouse:275, movetoworkspace, 6"
              "$mainMod SHIFT ALT, mouse:275, movetoworkspace, 7"
              "$mainMod CTRL, mouse:276, movetoworkspacesilent, 5"
              "$mainMod CTRL, mouse:275, movetoworkspacesilent, 6"
              "$mainMod CTRL ALT, mouse:275, movetoworkspacesilent, 7"

              # Rebuild NixOS
              "$mainMod, U, exec, $term -e rebuild"

              # Scroll workspaces
              "$mainMod, mouse_down, workspace, e+1"
              "$mainMod, mouse_up,   workspace, e-1"

              # Move active window
              "$mainMod CTRL ALT, right, movetoworkspace, r+1"
              "$mainMod CTRL ALT, left,  movetoworkspace, r-1"
              "$mainMod SHIFT $CONTROL, left,  movewindow, l"
              "$mainMod SHIFT $CONTROL, right, movewindow, r"
              "$mainMod SHIFT $CONTROL, up,    movewindow, u"
              "$mainMod SHIFT $CONTROL, down,  movewindow, d"
              "$mainMod SHIFT $CONTROL, H, movewindow, l"
              "$mainMod SHIFT $CONTROL, L, movewindow, r"
              "$mainMod SHIFT $CONTROL, K, movewindow, u"
              "$mainMod SHIFT $CONTROL, J, movewindow, d"

              # Scratchpad
              "$mainMod CTRL, S, movetoworkspacesilent, special"
              "$mainMod ALT, S,  movetoworkspacesilent, special"
              "$mainMod, S,      togglespecialworkspace,"
            ]
            ++ (builtins.concatLists (
              builtins.genList (
                x:
                let
                  ws = let c = (x + 1) / 10; in builtins.toString (x + 1 - (c * 10));
                in
                [
                  "$mainMod, ${ws},           workspace,            ${toString (x + 1)}"
                  "$mainMod SHIFT, ${ws},     movetoworkspace,      ${toString (x + 1)}"
                  "$mainMod CTRL, ${ws},      movetoworkspacesilent, ${toString (x + 1)}"
                ]
              ) 10
            ));

            bindm = [
              "$mainMod, mouse:272, movewindow"
              "$mainMod, mouse:273, resizewindow"
            ];

            binds = {
              workspace_back_and_forth = 1; # Personal preference
            };

            monitor = [
              "eDP-1,1920x1080@60,0x0,1"                                                          # Laptop screen
              "desc:BNQ BenQ EW277HDR 99J01861SL0,preferred,-1920x0,1"
              "desc:BNQ BenQ EL2870U PCK00489SL0,preferred,0x0,2"
              "desc:BNQ BenQ xl2420t 99D06760SL0,preferred,1920x-420,1,transform,1"
              ",preferred,auto,1"                                                                   # Fallback
            ];

            workspace = [
              "1, persistent:true, monitor:desc:BNQ BenQ EL2870U PCK00489SL0, default:true"
              "2, persistent:true, monitor:desc:BNQ BenQ EL2870U PCK00489SL0"
              "3, persistent:true, monitor:desc:BNQ BenQ EL2870U PCK00489SL0"
              "4, persistent:true, monitor:desc:BNQ BenQ EL2870U PCK00489SL0"
              "5, persistent:true, monitor:desc:BNQ BenQ EW277HDR 99J01861SL0, default:true"
              "6, persistent:true, monitor:desc:BNQ BenQ EW277HDR 99J01861SL0"
              "7, persistent:true, monitor:desc:BNQ BenQ EW277HDR 99J01861SL0"
              "8, persistent:true, monitor:desc:BNQ BenQ xl2420t 99D06760SL0, default:true"
              "9, persistent:true, monitor:desc:BNQ BenQ xl2420t 99D06760SL0"
              "10, persistent:true, monitor:desc:BNQ BenQ EL2870U PCK00489SL0"
            ];
          };

          extraConfig = ''
            # Personal: lid switch — disable/enable laptop screen
            bindl=,switch:on:Lid Switch,exec,hyprctl keyword monitor "eDP-1, disable"
            bindl=,switch:off:Lid Switch,exec,hyprctl keyword monitor "eDP-1, 1920x1080@60, 0x0, 1"
          '';
        };
      }
    )
  ];
}
