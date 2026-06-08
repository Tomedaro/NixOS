{ pkgs, lib, ... }:
{
  home-manager.sharedModules = [
    (_: {
      xdg.configFile."kitty/themes/amber-cathode.conf".source =
        ./themes/amber-cathode.conf;

      programs.kitty = {
        enable = true;

        font = {
          size = 14.0;
          name = "monospace";
        };

        # Do not use themeFile here: Home Manager's themeFile is for
        # pkgs.kitty-themes, not local custom theme files.
        #
        # Put this after generated settings so theme colors win over any
        # accidental color settings elsewhere.
        extraConfig = lib.mkAfter ''
          include themes/amber-cathode.conf
        '';

        settings = {
          # shell = "${pkgs.lib.getExe pkgs.tmux}";

          cursor_trail = 5;
          cursor_trail_decay = "0.03 0.2";
          strip_trailing_spaces = "smart";
          macos_option_as_alt = "yes";
          macos_quit_when_last_window_closed = true;
          copy_on_select = "yes";
          confirm_os_window_close = 0;
          scrollback_lines = 10000;
          enable_audio_bell = false;
          mouse_hide_wait = 60;
          update_check_interval = 0;

          # Tabs
          tab_title_template = "{index}";
          active_tab_font_style = "normal";
          inactive_tab_font_style = "normal";
          tab_bar_style = "powerline";
          tab_powerline_style = "round";

          # Color values moved into themes/amber-cathode.conf:
          # active_tab_foreground
          # active_tab_background
          # inactive_tab_foreground
          # inactive_tab_background
        };

        # shellIntegration.mode = "no-sudo";

        keybindings = {
          "ctrl+alt+n" = "launch --cwd=current";
          "alt+w" = "copy_and_clear_or_interrupt";
          "ctrl+y" = "paste_from_clipboard";

          "alt+1" = "goto_tab 1";
          "alt+2" = "goto_tab 2";
          "alt+3" = "goto_tab 3";
          "alt+4" = "goto_tab 4";
          "alt+5" = "goto_tab 5";
          "alt+6" = "goto_tab 6";
          "alt+7" = "goto_tab 7";
          "alt+8" = "goto_tab 8";
          "alt+9" = "goto_tab 9";
          "alt+0" = "goto_tab 10";

          # Tmux
          "ctrl+t" = "launch --cwd=current --type=overlay tmux-sessionizer";
          # "ctrl+t" = "launch --cwd=current --title tmux-sessionizer tmux-sessionizer";

          "ctrl+shift+left" = "no_op";
          "ctrl+shift+right" = "no_op";
        };
      };
    })
  ];
}
