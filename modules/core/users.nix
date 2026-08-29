{
  choices,
  config,
  pkgs,
  inputs,
  ...
}: let
  username = config.workstation.user.name;
  inherit
    (config.workstation.apps)
    editor
    terminal
    browser
    shell
    ;

  editorCommand = choices.editors.${editor}.command;
  browserCommand = choices.browsers.${browser}.command;
  terminalCommand = choices.terminals.${terminal}.command;
  shellPackageName = choices.shells.${shell}.packageName;
  homeManagerUsers = builtins.attrNames config.home-manager.users;
in {
  imports = [inputs.home-manager.nixosModules.home-manager];

  assertions = [
    {
      assertion = homeManagerUsers == [username];
      message = ''
        This workstation intentionally uses home-manager.sharedModules under a
        single-user Home Manager contract. Expected exactly the primary user
        '${username}', but found: ${builtins.concatStringsSep ", " homeManagerUsers}
      '';
    }
  ];

  programs.dconf.enable = true;

  home-manager = {
    useGlobalPkgs = true;
    useUserPackages = true;
    overwriteBackup = true;
    backupFileExtension = "backup";
    users.${username} = {
      programs.home-manager.enable = true;
      xdg.enable = true;

      home = {
        stateVersion = "26.05"; # Intentionally migrated from 23.11; see docs/state-version-26.05.md
        sessionVariables = {
          EDITOR = editorCommand;
          VISUAL = editorCommand;
          BROWSER = browserCommand;
          TERMINAL = terminalCommand;
        };
      };
    };
  };

  users = {
    mutableUsers = true;
    users.${username} = {
      isNormalUser = true;
      extraGroups = [
        "wheel" # sudo access
        "input"
        "networkmanager"
        "video"
        "audio"
        "libvirtd"
        "kvm"
      ];
      shell = pkgs.${shellPackageName};
      ignoreShellProgramCheck = true;
    };
  };

  nix.settings.allowed-users = [username];
}
