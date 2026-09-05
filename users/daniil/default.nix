{
  choices,
  devShellsPath,
  mkMcpNixos,
  nixpkgsSource,
  nixvimPackages,
  nvchadModule,
  spicetifyModule,
  spicetifyPackages,
  thunderbirdTheme,
  userSelections,
}: let
  selectChoice = kind: set: name: let
    choice = set.${name} or (throw "Unknown ${kind} choice: ${name}");
  in
    if choice.status == "supported"
    then choice
    else throw "${kind} choice '${name}' is ${choice.status}: ${choice.reason}";

  terminalChoice = selectChoice "terminal" choices.terminals userSelections.terminal;
  editorChoice = selectChoice "editor" choices.editors userSelections.editor;
  browserChoice = selectChoice "browser" choices.browsers userSelections.browser;
  fileManagerChoice = selectChoice "file manager" choices.fileManagers userSelections.fileManager;
  shellChoice = selectChoice "shell" choices.shells userSelections.shell;

  homeModuleArgs = {
    inherit devShellsPath nixpkgsSource nixvimPackages nvchadModule;
    terminal = userSelections.terminal;
  };
in {
  _class = "homeManager";

  imports = [
    ./packages.nix
    ../../modules/programs/media/discord
    ../../modules/programs/cli/starship
    ../../modules/programs/cli/tmux
    ../../modules/programs/cli/lazygit
    ../../modules/programs/cli/cava
    ../../modules/programs/cli/direnv
    ../../modules/programs/cli/btop
    (import ../../modules/programs/cli/pi {inherit mkMcpNixos;})
    ../../modules/programs/media/obs-studio
    ../../modules/programs/media/mpv
    (import ../../modules/programs/media/spicetify {
      inherit spicetifyModule spicetifyPackages;
    })
    (import ../../modules/programs/media/thunderbird {
      inherit thunderbirdTheme;
    })
    (terminalChoice.homeModule homeModuleArgs)
    (editorChoice.homeModule homeModuleArgs)
    (fileManagerChoice.homeModule homeModuleArgs)
    (shellChoice.homeModule homeModuleArgs)
  ];

  home.sessionVariables = {
    EDITOR = editorChoice.command;
    VISUAL = editorChoice.command;
    BROWSER = browserChoice.command;
    TERMINAL = terminalChoice.command;
  };

  # Reusable personal Home Manager baseline. Installation-specific compatibility
  # state (home.stateVersion) belongs to the concrete user@host integration.
  programs.home-manager.enable = true;
  xdg.enable = true;
}
