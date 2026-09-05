{
  choices,
  clock24h,
  terminal,
  waybarTheme,
}: {...}: let
  theme = waybarTheme;
  themeChoice = choices.waybarThemes.${theme} or (throw "Unknown Waybar theme choice: ${theme}");
  themeModule =
    if themeChoice.status == "supported"
    then themeChoice.homeModule {inherit clock24h terminal;}
    else throw "Waybar theme choice '${theme}' is ${themeChoice.status}: ${themeChoice.reason}";
in {
  _class = "homeManager";

  imports = [themeModule];
}
