{
  choices,
  workstationSettings,
  ...
}: let
  theme = workstationSettings.waybarTheme;
  themeChoice = choices.waybarThemes.${theme} or (throw "Unknown Waybar theme choice: ${theme}");
  themeModule =
    if themeChoice.status == "supported"
    then themeChoice.module
    else throw "Waybar theme choice '${theme}' is ${themeChoice.status}: ${themeChoice.reason}";
in {
  imports = [themeModule];
}
