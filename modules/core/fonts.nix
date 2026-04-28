{ pkgs, ... }:
{
  fonts = {
    fontDir.enable = true;
    packages = with pkgs; [
      # Nerd Fonts
      maple-mono.NF
      pkgs.nerd-fonts.jetbrains-mono

      # Normal Fonts
      noto-fonts
      noto-fonts-color-emoji

      # CJK Fonts
      noto-fonts-cjk-sans    # ← add
      noto-fonts-cjk-serif   # ← add
    ];
    fontconfig = {
      enable = true;
      antialias = true;
      hinting = {
        enable = true;
        style = "slight";       # ← add, best for CJK
      };
      defaultFonts = {
        monospace = [
          "JetBrainsMono Nerd Font"
          "Maple Mono NF"
          "Noto Sans Mono CJK SC"  # ← add before Noto Mono
          "Noto Mono"
          "DejaVu Sans Mono"
        ];
        sansSerif = [
          "Noto Sans CJK SC"       # ← add first
          "Noto Sans"
          "DejaVu Sans"
        ];
        serif = [
          "Noto Serif CJK SC"      # ← add first
          "Noto Serif"
          "DejaVu Serif"
        ];
        emoji = [ "Noto Color Emoji" ];
      };
    };
  };
}
