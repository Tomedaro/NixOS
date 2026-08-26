{
  description = "A simple flake for an atomic system";

  inputs = {
    nixpkgs.url        = "github:nixos/nixpkgs/nixos-unstable";
    nixpkgs-stable.url = "github:nixos/nixpkgs/nixos-25.11"; # upstream: updated from 24.11
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
    nur.url = "github:nix-community/NUR";
    betterfox = {
      url    = "github:yokoffing/Betterfox";
      flake  = false;
    };
    thunderbird-catppuccin = {
      url   = "github:catppuccin/thunderbird";
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

  outputs =
    {
      self,
      nixpkgs,
      ...
    } @ inputs:
    let
      inherit (self) outputs;
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;

      templates = import ./dev-shells;
      devShellEntries = builtins.readDir ./dev-shells;
      templateDirectories =
        builtins.filter
          (name:
            devShellEntries.${name} == "directory"
            && builtins.pathExists (./dev-shells + "/${name}/flake.nix"))
          (builtins.attrNames devShellEntries);
      registeredTemplateDirectories =
        nixpkgs.lib.unique
          (map
            (template: builtins.baseNameOf (toString template.path))
            (builtins.attrValues templates));
      templateRegistryIsComplete =
        builtins.sort builtins.lessThan templateDirectories
        == builtins.sort builtins.lessThan registeredTemplateDirectories;

      mkHost = host:
        nixpkgs.lib.nixosSystem {
          system = "x86_64-linux";
          modules = [
            ./hosts/${host}/configuration.nix
          ];
          specialArgs = {
            overlays = import ./overlays { inherit inputs host; };
            inherit self inputs outputs host;
          };
        };
    in
    {
      templates = templates;
      overlays = import ./overlays { inherit inputs; host = "Default"; };
      formatter = forAllSystems (system: nixpkgs.legacyPackages.${system}.alejandra);

      nixosConfigurations = {
        Default = mkHost "Default";
      };

      checks.x86_64-linux =
        let
          pkgs = nixpkgs.legacyPackages.x86_64-linux;
        in
        {
          system = self.nixosConfigurations.Default.config.system.build.toplevel;

          formatting = pkgs.runCommand "nix-formatting-check" {
            nativeBuildInputs = [ pkgs.alejandra pkgs.findutils ];
            src = ./.;
          } ''
            cd "$src"
            find . -type f -name '*.nix' -print0 \
              | xargs -0 -r alejandra --check
            touch "$out"
          '';

          template-registry =
            assert templateRegistryIsComplete;
            pkgs.runCommand "template-registry-check" { } ''
              touch "$out"
            '';
        };

      devShells = forAllSystems (system:
        let
          pkgs = import nixpkgs {
            inherit system;
            config.allowUnfree = true;
            config.nvidia.acceptLicense = true;
          };
        in {
          default = pkgs.mkShellNoCC {
            packages = with pkgs; [ git nix figlet lolcat ];
            NIX_CONFIG = "experimental-features = nix-command flakes";
          };
        });
    };
}
