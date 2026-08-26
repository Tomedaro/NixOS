{
  description = "A simple flake for an atomic system";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixos-unstable";
    hyprland.url = "github:hyprwm/Hyprland";

    home-manager = {
      url = "github:nix-community/home-manager";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nix-index-database = {
      url = "github:nix-community/nix-index-database";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Editors
    nixvim = {
      url = "github:niksingh710/nvix"; # Personal fork — keep yours
      inputs.nixpkgs.follows = "nixpkgs";
    };
    nvchad4nix = {
      url = "github:nix-community/nix4nvchad";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Browser
    zen-browser = {
      url = "github:0xc000022070/zen-browser-flake"; # upstream: updated URL
      inputs = {
        nixpkgs.follows = "nixpkgs";
        home-manager.follows = "home-manager";
      };
    };

    # Theming / Media
    spicetify-nix = {
      url = "github:Gerg-L/spicetify-nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    betterfox = {
      url = "github:yokoffing/Betterfox";
      flake = false;
    };
    thunderbird-catppuccin = {
      url = "github:catppuccin/thunderbird";
      flake = false;
    };

    # MCP tooling
    mcp-nixos = {
      url = "github:utensils/mcp-nixos";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # AI agent packages
    llm-agents = {
      url = "github:numtide/llm-agents.nix";
      inputs.nixpkgs.follows = "nixpkgs";
    };

    # Personal inputs
    yt-x = {
      url = "github:Benexl/yt-x";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    bzmenu.url = "github:e-tho/bzmenu";
  };

  outputs = {
    self,
    nixpkgs,
    ...
  } @ inputs: let
    inherit (self) outputs;
    lib = nixpkgs.lib;
    choices = import ./lib/choices.nix;
    systems = [
      "x86_64-linux"
      "aarch64-linux"
    ];
    forAllSystems = lib.genAttrs systems;

    templates = import ./dev-shells;
    devShellEntries = builtins.readDir ./dev-shells;
    templateDirectories =
      builtins.filter
      (name:
        devShellEntries.${name}
        == "directory"
        && builtins.pathExists (./dev-shells + "/${name}/flake.nix"))
      (builtins.attrNames devShellEntries);
    registeredTemplateDirectories =
      lib.unique
      (map
        (template: builtins.baseNameOf (toString template.path))
        (builtins.attrValues templates));
    templateRegistryIsComplete =
      builtins.sort builtins.lessThan templateDirectories
      == builtins.sort builtins.lessThan registeredTemplateDirectories;

    supportedNames = set:
      builtins.attrNames (lib.filterAttrs (_: choice: choice.status == "supported") set);

    mkHost = {
      host,
      settingsOverride ? {},
    }: let
      baseWorkstationSettings = import ./hosts/${host}/variables.nix;
      workstationSettings = lib.recursiveUpdate baseWorkstationSettings settingsOverride;
    in
      lib.nixosSystem {
        system = "x86_64-linux";
        modules = [./hosts/${host}/configuration.nix];
        specialArgs = {
          overlays = import ./overlays {inherit inputs;};
          inherit self inputs outputs host workstationSettings choices;
        };
      };

    variantsFor = {
      prefix,
      set,
      override,
    }:
      lib.listToAttrs (
        map
        (name: lib.nameValuePair "${prefix}-${name}" (override name))
        (supportedNames set)
      );

    supportedVariantOverrides =
      variantsFor {
        prefix = "desktop";
        set = choices.desktops;
        override = desktop: {inherit desktop;};
      }
      // variantsFor {
        prefix = "bar";
        set = choices.hyprlandBars;
        override = bar: {
          desktop = "hyprland";
          inherit bar;
        };
      }
      // variantsFor {
        prefix = "waybar-theme";
        set = choices.waybarThemes;
        override = waybarTheme: {
          desktop = "hyprland";
          bar = "waybar";
          inherit waybarTheme;
        };
      }
      // variantsFor {
        prefix = "terminal";
        set = choices.terminals;
        override = terminal: {inherit terminal;};
      }
      // variantsFor {
        prefix = "editor";
        set = choices.editors;
        override = editor: {inherit editor;};
      }
      // variantsFor {
        prefix = "file-manager";
        set = choices.fileManagers;
        override = fileManager: {inherit fileManager;};
      }
      // variantsFor {
        prefix = "shell";
        set = choices.shells;
        override = shell: {inherit shell;};
      }
      // variantsFor {
        prefix = "video";
        set = choices.videoDrivers;
        override = videoDriver: {inherit videoDriver;};
      }
      // {
        gaming-disabled = {games = false;};
      };

    validChoiceStatuses = [
      "supported"
      "pending"
      "legacy"
      "experimental"
    ];
    choiceSets = [
      choices.desktops
      choices.hyprlandBars
      choices.waybarThemes
      choices.terminals
      choices.editors
      choices.browsers
      choices.fileManagers
      choices.shells
      choices.videoDrivers
    ];
    choiceCatalogIsValid =
      lib.all
      (set:
        lib.all
        (choice:
          choice ? module
          && choice ? status
          && builtins.elem choice.status validChoiceStatuses
          && (choice.status == "supported" || choice ? reason))
        (builtins.attrValues set))
      choiceSets
      && lib.all (choice: choice ? command) (builtins.attrValues choices.terminals)
      && lib.all (choice: choice ? command) (builtins.attrValues choices.editors)
      && lib.all (choice: choice ? command) (builtins.attrValues choices.browsers)
      && lib.all (choice: choice ? packageName) (builtins.attrValues choices.shells);
  in {
    templates = templates;
    overlays = import ./overlays {inherit inputs;};
    formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.alejandra);

    nixosConfigurations = {
      Default = mkHost {host = "Default";};
    };

    checks.x86_64-linux = let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      mkVariantEvaluationCheck = name: settingsOverride: let
        configuration = mkHost {
          host = "Default";
          inherit settingsOverride;
        };
      in
        builtins.seq configuration.config.system.build.toplevel.drvPath (
          pkgs.runCommand "variant-${name}-evaluation" {} ''
            touch "$out"
          ''
        );
    in
      {
        system = self.nixosConfigurations.Default.config.system.build.toplevel;

        formatting =
          pkgs.runCommand "nix-formatting-check" {
            nativeBuildInputs = [pkgs.alejandra pkgs.findutils];
            src = ./.;
          } ''
            cd "$src"
            find . -type f -name '*.nix' -print0 \
              | xargs -0 -r alejandra --check
            touch "$out"
          '';

        template-registry = assert templateRegistryIsComplete;
          pkgs.runCommand "template-registry-check" {} ''
            touch "$out"
          '';

        workstation-boundary =
          pkgs.runCommand "workstation-boundary-check" {
            nativeBuildInputs = [pkgs.ripgrep];
            src = ./.;
          } ''
            if rg -n 'hosts/.*/variables\.nix' "$src/modules" --glob '*.nix'; then
              echo "ordinary modules must consume config.workstation, not host variables.nix" >&2
              exit 1
            fi
            touch "$out"
          '';

        choice-catalog = assert choiceCatalogIsValid;
          pkgs.runCommand "workstation-choice-catalog-check" {} ''
            touch "$out"
          '';
      }
      // lib.mapAttrs' (
        name: settingsOverride:
          lib.nameValuePair "variant-${name}" (mkVariantEvaluationCheck name settingsOverride)
      )
      supportedVariantOverrides;

    devShells = forAllSystems (system: let
      pkgs = import nixpkgs {
        inherit system;
        config.allowUnfree = true;
        config.nvidia.acceptLicense = true;
      };
    in {
      default = pkgs.mkShellNoCC {
        packages = with pkgs; [
          git
          nix
          figlet
          lolcat
        ];
        NIX_CONFIG = "experimental-features = nix-command flakes";
      };
    });
  };
}
