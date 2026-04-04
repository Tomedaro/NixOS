<<<<<<< HEAD
{...}: {
=======
{ pkgs, ... }:
let
  gamemode = pkgs.callPackage ../../scripts/gamemode.nix { };
  togglepowermode = pkgs.callPackage ../../scripts/togglepowermode.nix { };
in
{
>>>>>>> upstream/master
  #  use later
  home-manager.sharedModules = [
    (_: {
      services.swaync = {
        enable = true;
        settings = {
          "$schema" = "/etc/xdg/swaync/configSchema.json";
          positionX = "right";
          positionY = "top";
          cssPriority = "user";
<<<<<<< HEAD
          control-center-margin-top = 22;
          control-center-margin-bottom = 2;
          control-center-margin-right = 1;
          control-center-margin-left = 0;
          notification-icon-size = 64;
          notification-body-image-height = 128;
=======
          control-center-margin-top = 10;
          control-center-margin-bottom = 10;
          control-center-margin-right = 10;
          control-center-margin-left = 0;
          notification-icon-size = 64;
          notification-body-image-height = 100;
>>>>>>> upstream/master
          notification-body-image-width = 200;
          timeout = 6;
          timeout-low = 3;
          timeout-critical = 0;
          fit-to-screen = false;
          control-center-width = 400;
<<<<<<< HEAD
          control-center-height = 915;
=======
          control-center-height = 940;
>>>>>>> upstream/master
          notification-window-width = 375;
          keyboard-shortcuts = true;
          image-visibility = "when-available";
          transition-time = 200;
          hide-on-clear = false;
          hide-on-action = true;
          script-fail-notify = true;
          widgets = [
            "title"
            "dnd"
            "menubar#desktop"
            "volume"
            "mpris"
            "notifications"
<<<<<<< HEAD
=======
            "buttons-grid"
>>>>>>> upstream/master
          ];
          widget-config = {
            title = {
              text = " Quick settings";
              clear-all-button = true;
              button-text = "";
            };
            "menubar#desktop" = {
<<<<<<< HEAD
              "menu#screenshot" = {
                label = "\t󰄀   Screenshot\t";
=======
              "backlight" = {
                label = "       󰃟  ";
              };
              "menu#screenshot" = {
                label = "󰄀  Screenshot";
>>>>>>> upstream/master
                position = "left";
                actions = [
                  {
                    label = "Whole screen";
<<<<<<< HEAD
                    command = "sh -c 'swaync-client -cp; sleep 1; grimblast copysave output \"/tmp/screenshot.png\"; swappy -f \"/tmp/screenshot.png\"'";
                  }
                  {
                    label = "Whole window / Select region";
                    command = "sh -c 'swaync-client -cp; grimblast copysave area \"/tmp/screenshot.png\"; swappy -f \"/tmp/screenshot.png\"'";
=======
                    command = "sh -c 'swaync-client -cp; sleep 1; ${pkgs.grimblast}/bin/grimblast copysave output \"/tmp/screenshot.png\"; ${pkgs.swappy}/bin/swappy -f \"/tmp/screenshot.png\"'";
                  }
                  {
                    label = "Whole window / Select region";
                    command = "sh -c 'swaync-client -cp; ${pkgs.grimblast}/bin/grimblast copysave area \"/tmp/screenshot.png\"; ${pkgs.swappy}/bin/swappy -f \"/tmp/screenshot.png\"'";
>>>>>>> upstream/master
                  }
                ];
              };
              "menu#power" = {
<<<<<<< HEAD
                label = "\t   Power Menu\t  ";
                position = "left";
                actions = [
                  {
                    label = "   Logout";
                    command = "hyprctl dispatch exit 0";
                  }
                  {
                    label = "   Shut down";
                    command = "systemctl poweroff";
                  }
                  {
                    label = "󰤄   Suspend";
                    command = "systemctl suspend";
                  }
                  {
                    label = "   Reboot";
                    command = "systemctl reboot";
=======
                label = "  Power Menu";
                position = "left";
                actions = [
                  {
                    label = "  Shut down";
                    command = "systemctl poweroff";
                  }
                  {
                    label = "  Reboot";
                    command = "systemctl reboot";
                  }
                  {
                    label = "󰤄  Suspend";
                    command = "systemctl suspend";
                  }
                  {
                    label = "  Logout";
                    command = "hyprctl dispatch exit 0";
                  }
                  {
                    label = "  Lock";
                    command = "hyprlock";
>>>>>>> upstream/master
                  }
                ];
              };
            };
            volume = {
              label = "";
              expand-button-label = "";
              collapse-button-label = "";
              show-per-app = true;
              show-per-app-icon = true;
              show-per-app-label = true;
            };
            dnd = {
              text = " Do Not Disturb";
            };
            mpris = {
              image-size = 96;
              image-radius = 4;
            };
<<<<<<< HEAD
            label = {
              text = "Notifications";
              clear-all-button = true;
              button-text = "";
=======
            notifications = {
              text = "Notifications";
              clear-all-button = true;
              button-text = " Clear";
            };

            "buttons-grid" = {
              actions = [
                {
                  label = "󰝟";
                  type = "toggle";
                  command = "${pkgs.pamixer}/bin/pamixer -t";
                  update-command = "sh -c '${pkgs.pamixer}/bin/pamixer --get-mute | grep -q true && echo true || echo false'";
                }
                {
                  label = "󰍭";
                  type = "toggle";
                  command = "${pkgs.pamixer}/bin/pamixer --default-source -t";
                  update-command = "sh -c '${pkgs.pamixer}/bin/pamixer --get-mute --default-source | grep true && echo true || echo false'";
                }

                {
                  label = "";
                  type = "toggle";
                  command = "blueman-manager";
                  update-command = "sh -c 'bluetoothctl show | grep -q \\\"Powered: yes\\\" && echo true || echo false'";
                }

                {
                  label = "󰤨";
                  type = "toggle";
                  command = "sh -c '[ \"$SWAYNC_TOGGLE_STATE\" = true ] && nmcli radio wifi on || nmcli radio wifi off'";
                  update-command = "sh -c 'nmcli radio wifi | grep -q enabled && echo true || echo false'";
                }

                {
                  label = "🎮";
                  type = "toggle";
                  command = "${gamemode}/bin/gamemode";
                  update-command = "hyprctl getoption animations:enabled | grep -q 'int: 1' && echo false || echo true";
                }

                {
                  label = "󰤄";
                  type = "toggle";
                  command = "sh -c '${pkgs.procps}/bin/pgrep -x hyprsunset >/dev/null && ${pkgs.procps}/bin/pkill hyprsunset || nohup ${pkgs.hyprsunset}/bin/hyprsunset --temperature 3500 > /tmp/hyprsunset_output.log 2>&1 &'";
                  update-command = "sh -c 'pgrep -x hyprsunset >/dev/null && echo true || echo false'";
                }

                {
                  label = "☕";
                  command = "systemctl --user is-active --quiet hypridle.service && systemctl --user stop hypridle.service || systemctl --user start hypridle.service";
                  type = "toggle";
                  update-command = "pgrep -x hypridle > /dev/null && echo false || echo true";
                }

                {
                  label = "";
                  type = "toggle";

                  command = "${togglepowermode}/bin/togglepowermode";
                  update-command = "test -f \"$HOME/.config/hypr/power_mode\" && grep -q \"^powersave$\" \"$HOME/.config/hypr/power_mode\" && echo true || echo false";
                }
              ];
>>>>>>> upstream/master
            };
          };
          scripts = {
            example-script = {
              exec = "echo 'Do something...'";
              urgency = "Normal";
            };
          };
          notification-visibility = {
            spotify = {
              state = "enabled";
              urgency = "Low";
              app-name = "Spotify";
            };
<<<<<<< HEAD
          };
        };
        style = ''
                    @define-color shadow rgba(0, 0, 0, 0.25);
=======
            youtube-music = {
              state = "enabled";
              urgency = "Low";
              app-name = "com.github.th_ch.youtube_music";
            };
          };
        };
        style = ''
          @define-color shadow rgba(0, 0, 0, 0.25);
>>>>>>> upstream/master
          /*
          *
          * Catppuccin Mocha palette
          * Maintainer: rubyowo
          *
          */

          @define-color base   #1E1D2E;
          @define-color mantle #181825;
          @define-color crust  #11111b;

          @define-color text     #cdd6f4;
          @define-color subtext0 #a6adc8;
          @define-color subtext1 #bac2de;

          @define-color surface0 #313244;
          @define-color surface1 #45475a;
          @define-color surface2 #585b70;

          @define-color overlay0 #6c7086;
          @define-color overlay1 #7f849c;
          @define-color overlay2 #9399b2;

          @define-color blue      #89b4fa;
          @define-color lavender  #b4befe;
          @define-color sapphire  #74c7ec;
          @define-color sky       #89dceb;
          @define-color teal      #94e2d5;
          @define-color green     #a6e3a1;
          @define-color yellow    #f9e2af;
          @define-color peach     #fab387;
          @define-color maroon    #eba0ac;
          @define-color red       #f38ba8;
          @define-color mauve     #cba6f7;
          @define-color pink      #f5c2e7;
          @define-color flamingo  #f2cdcd;
          @define-color rosewater #f5e0dc;

          @define-color base_lighter  #1e1e2e;
          @define-color mauve_lighter #caa6f7;

          * {
<<<<<<< HEAD
            font-family: "Product Sans";
            background-clip: border-box;
          }

          /* #notifications_box { */
          /*   border: solid 4px red; */
          /* } */

          label {
            color: @text;
          }

          .notification {
            border: none;
            box-shadow: none;
            /* margin: 0px; */
            /* margin: -15px -10px -15px -10px; */
            border-radius: 4px;
            background: inherit;
            /* background: @theme_bg_color; */
            /* background: shade(alpha(@borders, 2.55), 0.25); */
          }

          .notification button {
            background: transparent;
            border-radius: 0px;
            border: none;
            margin: 0px;
            padding: 0px;
          }

          .notification button:hover {
            /* background: @surface0; */
            background: @insensitive_bg_color;
          }

          .notification-content {
            min-height: 64px;
            margin: 10px;
            padding: 0px;
            border-radius: 0px;
=======
            font-family: "JetBrainsMono NFM SemiBold", monospace;
            border-radius: 8px;
          }

          .notification {
            background: @theme_bg_color;
            border: 1px solid @theme_selected_bg_color;
            border-radius: 8px;
            margin: 6px 0;
          }

          .notification-action {
            border: 2px solid;
            border-top: none;
>>>>>>> upstream/master
          }

          .close-button {
            background: transparent;
            color: transparent;
          }

<<<<<<< HEAD
          .notification-default-action,
          .notification-action {
            background: transparent;
            border: none;
          }


          .notification-default-action {
            border-radius: 4px;
          }

          /* When alternative actions are visible */
          .notification-default-action:not(:only-child) {
            border-bottom-left-radius: 0px;
            border-bottom-right-radius: 0px;
          }

          .notification-action {
            border-radius: 0px;
            padding: 2px;
            color: @text;
            /* color: @theme_text_color; */
          }

          /* add bottom border radius to eliminate clipping */
          .notification-action:first-child {
            border-bottom-left-radius: 4px;
          }

          .notification-action:last-child {
            border-bottom-right-radius: 4px;
          }

          /*** Notification ***/
          /* Notification header */
          .summary {
            color: @text;
            /* color: @theme_text_color; */
            font-size: 14px;
            padding: 0px;
=======
          /*** Notification ***/
          /* Notification header */
          .summary {
            color: @theme_text_color;
            font-size: 16px;
            background: transparent;
            text-shadow: none;
            font-size: 16px;
>>>>>>> upstream/master
          }

          .time {
            color: @subtext0;
            /* color: alpha(@theme_text_color, 0.9); */
<<<<<<< HEAD
            font-size: 12px;
            text-shadow: none;
            margin: 0px 0px 0px 0px;
            padding: 2px 0px;
          }

          .body {
            font-size: 14px;
            font-weight: 500;
            color: @subtext1;
            /* color: alpha(@text, 0.9); */
            /* color: alpha(@theme_text_color, 0.9); */
            text-shadow: none;
            margin: 0px 0px 0px 0px;
          }

          .body-image {
            border-radius: 4px;
=======
            font-size: 16px;
            background: transparent;
            font-size: 16px;
            text-shadow: none;
            margin-right: 18px;
          }

          .body {
            background: transparent;
            font-size: 15px;
            font-weight: 500;
            color: @subtext1;
            /* color: alpha(@theme_text_color, 0.9); */
            text-shadow: none;
>>>>>>> upstream/master
          }

          /* The "Notifications" and "Do Not Disturb" text widget */
          .top-action-title {
<<<<<<< HEAD
            color: @text;
=======
            color: @theme_text_color;
>>>>>>> upstream/master
            /* color: @theme_text_color; */
            text-shadow: none;
          }

<<<<<<< HEAD
          /* Control center */

          .control-center {
            background: alpha(@crust, .80);
            border-radius: 15px;
            border: 0px solid @selected;
            box-shadow: 0 0 10px 0 rgba(0,0,0,.80);
            margin: 10px;
            padding: 4px;
          }

          /* .right.overlay-indicator { */
          /*   border: solid 5px red; */
          /* } */

          .control-center-list {
            /* background: @base; */
            background: alpha(@crust, .80);
            min-height: 5px;
            /* border: 1px solid @surface1; */
            border-top: none;
            border-radius: 0px 0px 4px 4px;
          }

          .control-center-list-placeholder,
          .notification-group-icon,
          .notification-group {
            /* opacity: 1.0; */
            /* opacity: 0; */
            color: alpha(@theme_text_color, 0.50);
          }

          .notification-group {
            /* unset the annoying focus thingie */
            opacity: 0;
            box-shadow: none;
            /* selectable: no; */
          }

          .notification-group > box {
            all: unset;
            background: transparent;
            /* background: alpha(currentColor, 0.072); */
            padding: 4px;
            margin: 0px;
            /* margin: 0px -5px; */
            border: none;
            border-radius: 4px;
            box-shadow: none;
=======
          .control-center {
            background: alpha(@theme_bg_color, .80);
            border-radius: 8px;
            border: 1px solid @theme_selected_bg_color;
          }

          .control-center .notification-row:focus,
          .control-center .notification-row:hover {
            opacity: 1;
            border-radius: 8px;
>>>>>>> upstream/master
          }

          .notification-row {
            outline: none;
<<<<<<< HEAD
            transition: all 1s ease;
            background: alpha(@mantle, .80);
            /* background: @theme_bg_color; */
            border: 0px solid @crust;
            margin: 10px 5px 0px 5px;
            border-radius: 14px;
            /* box-shadow: 0px 0px 4px black; */
            /* background: alpha(currentColor, 0.05); */
          }

          .notification-row:focus,
          .notification-row:hover {
            box-shadow: none;
          }

          .control-center-list > row,
          .control-center-list > row:focus,
          .control-center-list > row:hover {
            background: transparent;
            border: none;
            margin: 0px;
            padding: 5px 10px 5px 10px;
            box-shadow: none;
          }

          .control-center-list > row:last-child {
            padding: 5px 10px 10px 10px;
          }


          /* Window behind control center and on all other monitors */
          .blank-window {
            background: transparent;
=======
            margin: 0;
            padding: 0;
            background: transparent;
            border: none;
            /* background: alpha(@mantle, .80); */
          }

          .notification-group {
            background: transparent;
            border: none;
>>>>>>> upstream/master
          }

          /*** Widgets ***/

          /* Title widget */
          .widget-title {
            margin: 0px;
            background: transparent;
            /* background: @theme_bg_color; */
            border-radius: 4px 4px 0px 0px;
            /* border: 1px solid @surface1; */
<<<<<<< HEAD
=======
            border-radius: 8px;
>>>>>>> upstream/master
            border-bottom: none;
          }

          .widget-title > label {
            margin: 18px 10px;
            font-size: 20px;
            font-weight: 500;
          }

          .widget-title > button {
            font-weight: 700;
            padding: 7px 3px;
            margin-right: 10px;
            background: transparent;
<<<<<<< HEAD
            color: @text;
            /* color: @theme_text_color; */
            border: none;
=======
            color: @theme_text_color;
            /* color: @theme_text_color; */
            border: none;
            /* border: none; */
>>>>>>> upstream/master
            border-radius: 4px;
          }
          .widget-title > button:hover {
            background: @base;
            /* background: alpha(currentColor, 0.1); */
          }

          /* Label widget */
          .widget-label {
            margin: 0px;
            padding: 0px;
            min-height: 5px;
<<<<<<< HEAD
            background: alpha(@mantle, .80);
=======
            background: alpha(@theme_bg_color, .80);
>>>>>>> upstream/master
            /* background: @theme_bg_color; */
            border-radius: 0px 0px 4px 4px;
            /* border: 1px solid @surface1; */
            border-top: none;
          }
          .widget-label > label {
            font-size: 15px;
            font-weight: 400;
          }

          /* Menubar */
          .widget-menubar {
            background: transparent;
            /* background: @theme_bg_color; */
            /* border: 1px solid @surface1; */
<<<<<<< HEAD
=======
            border-radius: 4px;
>>>>>>> upstream/master
            border-top: none;
            border-bottom: none;
          }
          .widget-menubar > box > box {
<<<<<<< HEAD
            margin: 5px 10px 5px 10px;
=======
            margin: 5px 5px 5px 5px;
>>>>>>> upstream/master
            min-height: 40px;
            border-radius: 4px;
            background: transparent;
          }
          .widget-menubar > box > box > button {
<<<<<<< HEAD
            background: alpha(@mantle, .80);
            /* background: alpha(currentColor, 0.05); */
            min-width: 185px;
            min-height: 50px;
            margin-right: 10px;
            font-size: 14px;
            padding: 0px;
          }
          .widget-menubar > box > box > button:nth-child(2) {
            margin-right: 0px;
          }
          .widget-menubar button:focus {
            box-shadow: none;
          }
          .widget-menubar button:focus:hover {
            background: @base;
=======
            background: alpha(@theme_bg_color, .80);
            /* background: alpha(currentColor, 0.05); */
            min-width: 185px;
            min-height: 50px;
            margin-right: 25px;
            font-size: 14px;
            padding: 5px;
          }
          .widget-menubar > box > box > button:nth-child(2) {
            margin-right: 0px;
            padding-top: 5px;
          }
          .widget-menubar button:hover {
            background: @theme_selected_bg_color;
>>>>>>> upstream/master
            /* background: alpha(currentColor,0.1); */
            box-shadow: none;
          }

          .widget-menubar > box > revealer > box {
            margin: 5px 10px 5px 10px;
<<<<<<< HEAD
            background: alpha(@mantle, .80);
=======
            background: alpha(@theme_bg_color, .80);
>>>>>>> upstream/master
            /* background: alpha(currentColor, 0.05); */
            border-radius: 4px;
          }
          .widget-menubar > box > revealer > box > button {
            background: transparent;
            min-height: 50px;
            padding: 0px;
            margin: 5px;
          }

          /* Buttons grid */
          .widget-buttons-grid {
            /* background-color: @theme_bg_color; */
            background: transparent;
            /* border: 1px solid @surface1; */
            border-top: none;
            border-bottom: none;
            font-size: 14px;
            font-weight: 500;
            margin: 0px;
<<<<<<< HEAD
            padding: 5px;
=======
            padding: 0px;
>>>>>>> upstream/master
            border-radius: 0px;
          }

          .widget-buttons-grid > flowbox > flowboxchild {
<<<<<<< HEAD
            background: alpha(@mantle, .80);
            /* background: alpha(currentColor, 0.05); */
            border-radius: 4px;
            min-height: 50px;
=======
            background: @theme_bg_color;
            /* background: alpha(currentColor, 0.05); */
            border-radius: 4px;
            min-height: 40px;
>>>>>>> upstream/master
            min-width: 85px;
            margin: 5px;
            padding: 0px;
          }

          .widget-buttons-grid > flowbox > flowboxchild > button {
            background: transparent;
            border-radius: 4px;
            margin: 0px;
            border: none;
            box-shadow: none;
          }


          .widget-buttons-grid > flowbox > flowboxchild > button:hover {
<<<<<<< HEAD
            background: alpha(@mantle, .80);
=======
            background: @theme_selected_bg_color;
>>>>>>> upstream/master
            /* background: alpha(currentColor, 0.1); */
          }

          /* Mpris widget */
          .widget-mpris {
            padding: 8px;
<<<<<<< HEAD
            padding-bottom: 15px;
            margin-bottom: -33px;
          }
          .widget-mpris > box {
            padding: 0px;
            margin: -5px 0px -10px 0px;
            padding: 0px;
            border-radius: 4px;
            /* background: alpha(currentColor, 0.05); */
            background: alpha(@mantle, .80);
          }
          .widget-mpris > box > button:nth-child(1),
          .widget-mpris > box > button:nth-child(3) {
            margin-bottom: 0px;
          }
          .widget-mpris > box > button:nth-child(1) {
            margin-left: -25px;
            margin-right: -25px;
            opacity: 0;
          }
          .widget-mpris > box > button:nth-child(3) {
            margin-left: -25px;
            margin-right: -25px;
            opacity: 0;
          }

          .widget-mpris-album-art {
            all: unset;
          }

          /* Player button box */
          .widget-mpris > box > carousel > widget > box > box:nth-child(2) {
            margin: 5px 0px -5px 90px;
          }

          /* Player buttons */
          .widget-mpris > box > carousel > widget > box > box:nth-child(2) > button {
            border-radius: 4px;
          }
          .widget-mpris > box > carousel > widget > box > box:nth-child(2) > button:hover {
            background: alpha(currentColor, 0.1);
          }
          carouselindicatordots {
            opacity: 0;
          }

          .widget-mpris-title {
            color: #eeeeee;
            font-weight: bold;
            font-size: 1.25rem;
            text-shadow: 0px 0px 5px rgba(0, 0, 0, 0.5);
          }
          .widget-mpris-subtitle {
            color: #eeeeee;
            font-size: 1rem;
            text-shadow: 0px 0px 3px rgba(0, 0, 0, 1);
          }

          .widget-mpris-player {
            border-radius: 0px;
            margin: 0px;
          }
          .widget-mpris-player > box > image {
            margin: 0px 0px -48px 0px;
          }

          .notification-group > box.vertical {
            /* border: solid 5px red; */
            margin-top: 3px
=======
            border-radius: 8px;
            padding-bottom: 15px;
            margin-bottom: 0px;
          }
          .widget-mpris > box > button,
          .widget-mpris-player,
          .widget-mpris-album-art, {
            box-shadow: none;
            margin: 10px 0 0 0;
            padding: 5px 10px;
            border-radius: 8px;
>>>>>>> upstream/master
          }

          /* Backlight and volume widgets */
          .widget-backlight,
          .widget-volume {
            background: transparent;
<<<<<<< HEAD
            /* background-color: @crust; */
            /* background-color: @theme_bg_color; */
            /* border: 1px solid @surface1; */
            border-top: none;
            border-bottom: none; font-size: 13px;
=======
            /* background-color: @theme_bg_color; */
            border-top: none;
            border-bottom: none;
            font-size: 13px;
>>>>>>> upstream/master
            font-weight: 600;
            border-radius: 0px;
            margin: 0px;
            padding: 0px;
          }
          .widget-volume > box {
<<<<<<< HEAD
            background: alpha(@mantle, .80);
=======
            background: alpha(@theme_bg_color, .80);
>>>>>>> upstream/master
            /* background: alpha(currentColor, 0.05); */
            border-radius: 4px;
            margin: 5px 10px 5px 10px;
            min-height: 50px;
          }
          .widget-volume > box > label {
            min-width: 50px;
            padding: 0px;
          }
          .widget-volume > box > button {
            min-width: 50px;
            box-shadow: none;
            padding: 0px;
          }
          .widget-volume > box > button:hover {
            /* background: alpha(currentColor, 0.05); */
            background: @surface0;
          }
          .widget-volume > revealer > list {
<<<<<<< HEAD
            background: alpha(@mantle, .80);
=======
            background: alpha(@theme_bg_color, .80);
>>>>>>> upstream/master
            /* background: alpha(currentColor, 0.05); */
            border-radius: 4px;
            margin-top: 5px;
            padding: 0px;
          }
          .widget-volume > revealer > list > row {
            padding-left: 10px;
            min-height: 40px;
            background: transparent;
          }
          .widget-volume > revealer > list > row:hover {
            background: transparent;
            box-shadow: none;
            border-radius: 4px;
          }
          .widget-backlight > scale {
<<<<<<< HEAD
            background: alpha(@mantle, .80);
=======
            background: alpha(@theme_bg_color, .80);
>>>>>>> upstream/master
            /* background: alpha(currentColor, 0.05); */
            border-radius: 0px 4px 4px 0px;
            margin: 5px 10px 5px 0px;
            padding: 0px 10px 0px 0px;
            min-height: 50px;
          }
          .widget-backlight > label {
            background: @surface0;
            /* background: alpha(currentColor, 0.05); */
            margin: 5px 0px 5px 10px;
            border-radius: 4px 0px 0px 4px;
            padding: 0px;
            min-height: 50px;
            min-width: 50px;
          }

          /* DND widget */
          .widget-dnd {
<<<<<<< HEAD
            margin: 6px;
=======
            margin: 6px 10px;
            padding: 0 12px;
>>>>>>> upstream/master
            font-size: 1.2rem;
          }

          .widget-dnd > switch {
<<<<<<< HEAD
            background: alpha(@mantle, .80);
=======
            background: alpha(@theme_bg_color, .80);
>>>>>>> upstream/master
            font-size: initial;
            border-radius: 8px;
            box-shadow: none;
            padding: 2px;
          }

          .widget-dnd > switch:hover {
<<<<<<< HEAD
            background: alpha(@mauve_lighter, .80);
          }

          .widget-dnd > switch:checked {
            background: @mauve;
          }

          .widget-dnd > switch:checked:hover {
            background: alpha(@mauve_lighter, .80);
          }

          .widget-dnd > switch slider {
            background: alpha(@mauve_lighter, .80);
=======
            background: alpha(@theme_selected_bg_color, .80);
          }

          .widget-dnd > switch:checked {
            background: @theme_fg_color;
          }

          .widget-dnd > switch:checked:hover {
            background: alpha(@theme_fg_color, .80);
          }

          .widget-dnd > switch slider {
            background: alpha(@theme_selected_bg_color, .80);
>>>>>>> upstream/master
            border-radius: 6px;
          }

          /* Toggles */
          .toggle:checked {
            background: @surface1;
            /* background: @theme_selected_bg_color; */
          }
          /*.toggle:not(:checked) {
            color: rgba(128, 128, 128, 0.5);
          }*/
          .toggle:checked:hover {
            background: @surface2;
            /* background: alpha(@theme_selected_bg_color, 0.75); */
          }

<<<<<<< HEAD
          /* Sliders */
          scale {
            padding: 0px;
            margin: 0px 10px 0px 10px;
          }

=======
>>>>>>> upstream/master
          scale trough {
            border-radius: 4px;
            background: @surface0;
            /* background: alpha(currentColor, 0.1); */
          }

<<<<<<< HEAD
          scale highlight {
            border-radius: 5px;
            min-height: 10px;
            margin-right: -5px;
          }

          scale slider {
            margin: -10px;
            min-width: 10px;
            min-height: 10px;
            background: transparent;
            box-shadow: none;
            padding: 0px;
=======
          scale slider {
            background: @theme_fg_color;
>>>>>>> upstream/master
          }
          scale slider:hover {
          }

<<<<<<< HEAD
          .right.overlay-indicator {
            all: unset;
=======
          /* Hide scrollbars */
          scrollbar,
          scrollbar * {
            all: unset;
            min-width: 0px;
            min-height: 0px;
          }

          scrollbar slider {
            background: transparent;
          }

          scrollbar.vertical,
          scrollbar.horizontal {
            background: transparent;
>>>>>>> upstream/master
          }
        '';
      };
    })
  ];
}
