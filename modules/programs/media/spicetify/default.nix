{
  inputs,
  lib,
  ...
}: {
  # allow spotify to be installed if you don't have unfree enabled already
  nixpkgs.config.allowUnfreePredicate = pkg:
    builtins.elem (lib.getName pkg) [
      "spotify"
    ];
  home-manager.sharedModules = [
    (
      {pkgs, ...}: let
        spicePkgs = inputs.spicetify-nix.legacyPackages.${pkgs.stdenv.hostPlatform.system};

        marketplaceTheme = pkgs.runCommand "spicetify-marketplace-theme" {} ''
          mkdir -p "$out"
          printf '[Marketplace]\n' > "$out/color.ini"
          touch "$out/user.css"
        '';
      in {
        # import the flake's module for your system
        imports = [inputs.spicetify-nix.homeManagerModules.default];

        # configure spicetify :)
        programs.spicetify = {
          enable = true;
          wayland = true;

          # Placeholder theme required by Spicetify Marketplace for runtime theme
          # installs. Marketplace-installed themes live in Spotify's browser
          # storage, not in the flake; extensions/apps remain declarative below.
          theme = {
            name = "marketplace";
            src = marketplaceTheme;
          };
          colorScheme = "Marketplace";

          # spotifywm is X11-only and noisy under Hyprland/Wayland; Hyprland
          # already matches Spotify without LD_PRELOAD window-class patching.
          windowManagerPatch = false;

          enabledExtensions = with spicePkgs.extensions; [
            adblockify
            hidePodcasts
            shuffle
            beautifulLyrics
            sleepTimer
            volumePercentage
          ];

          # Marketplace is browse/discover only in this flake-managed setup:
          # extensions must stay declared here to persist reproducibly.
          enabledCustomApps = with spicePkgs.apps; [
            marketplace
            newReleases
            lyricsPlus
          ];
        };
      }
    )
  ];
}
