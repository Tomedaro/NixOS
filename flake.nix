{
  description = "A simple flake for an atomic system";

  inputs = {
    nixpkgs.url        = "github:nixos/nixpkgs/nixos-unstable";
    nixpkgs-stable.url = "github:nixos/nixpkgs/nixos-25.11"; # upstream: updated from 24.11

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
      url = "github:Tomedaro/nixvim"; # Personal fork — keep yours
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

    # Personal inputs
    yt-x = {
      url = "github:Benexl/yt-x";
      inputs.nixpkgs.follows = "nixpkgs";
    };
    bzmenu = {
      url = "github:e-tho/bzmenu";
      inputs.nixpkgs.follows = "nixpkgs";
    };
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
      templates  = import ./dev-shells;
      overlays   = import ./overlays { inherit inputs; };
      formatter  = forAllSystems (system: nixpkgs.legacyPackages.${system}.alejandra);

      nixosConfigurations = {
        Default = mkHost "Default";
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
