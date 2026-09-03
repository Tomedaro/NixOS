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
        This workstation still has transitional home-manager.sharedModules, so
        it intentionally enforces a single managed Home Manager user. Expected
        exactly the primary user
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
    users.${username}.home.sessionVariables = {
      EDITOR = editorCommand;
      VISUAL = editorCommand;
      BROWSER = browserCommand;
      TERMINAL = terminalCommand;
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
