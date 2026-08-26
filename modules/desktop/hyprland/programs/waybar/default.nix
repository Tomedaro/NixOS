{
  choices,
  workstationSettings,
  ...
}: let
  theme = workstationSettings.waybarTheme;
  themeModule = choices.waybarThemes.${theme} or (throw "Unsupported Waybar theme choice: ${theme}");
in {
  imports = [themeModule];
}
