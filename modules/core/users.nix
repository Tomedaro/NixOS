{
  choices,
  config,
  pkgs,
  inputs,
  ...
}: let
  username = config.workstation.user.name;
  shell = config.workstation.apps.shell;
  shellPackageName = choices.shells.${shell}.packageName;
in {
  imports = [inputs.home-manager.nixosModules.home-manager];

  assertions = [
    {
      assertion = builtins.length config.home-manager.sharedModules == 0;
      message = ''
        Home Manager ownership: home-manager.sharedModules must stay empty.
        Import personal features into the intended user's composition instead.
        Dormant shared-module integrations must be migrated before activation.
      '';
    }
  ];

  programs.dconf.enable = true;

  home-manager = {
    useGlobalPkgs = true;
    useUserPackages = true;
    overwriteBackup = true;
    backupFileExtension = "backup";
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
