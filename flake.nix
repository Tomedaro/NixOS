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
    # Declarative Flatpak state. `latest` is pinned by flake.lock, so updates
    # remain explicit while following stable nix-flatpak releases.
    nix-flatpak.url = "github:gmodena/nix-flatpak/?ref=latest";

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
    lib = nixpkgs.lib;
    choices = import ./lib/choices.nix;
    repoOverlays = import ./overlays {inherit inputs;};

    # Systems on which the generic formatter/dev-shell outputs are exposed.
    # This is independent of each NixOS host target platform, which is owned by
    # nixpkgs.hostPlatform. Apps/checks remain explicitly x86_64-linux for now.
    toolSystems = ["x86_64-linux"];
    forAllToolSystems = lib.genAttrs toolSystems;

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
      # Only import-time selectors belong in specialArgs outside the host module.
      # `imports` is resolved before the module fixed point, so these values
      # cannot be sourced from config.workstation without recursion.
      workstationSelections = {
        inherit (workstationSettings) bar waybarTheme;
      };
    in
      lib.nixosSystem {
        modules = [
          ./hosts/${host}
          {
            networking.hostName = lib.mkDefault host;
            nixpkgs.overlays = [repoOverlays.default];

            # These values are ordinary module context, not import selectors.
            # Keep them out of specialArgs so the import-time boundary stays explicit.
            _module.args = {
              inherit self;
              nixosConfigurationName = host;
            };
          }
        ];
        specialArgs = {
          # Every value here is currently required while resolving imports.
          inherit inputs workstationSettings workstationSelections choices;
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

    baselineWorkstationSettings = import ./hosts/Singularity/variables.nix;
    isBaselineOverride = settingsOverride:
      lib.all
      (name:
        builtins.hasAttr name baselineWorkstationSettings
        && baselineWorkstationSettings.${name} == settingsOverride.${name})
      (builtins.attrNames settingsOverride);
    supportedAlternativeOverrides =
      lib.filterAttrs (_: settingsOverride: !isBaselineOverride settingsOverride)
      supportedVariantOverrides;
    supportedAlternativeNames = builtins.attrNames supportedAlternativeOverrides;

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
    overlays = repoOverlays;
    formatter = forAllToolSystems (system: nixpkgs.legacyPackages.${system}.alejandra);

    nixosConfigurations = {
      Singularity = mkHost {host = "Singularity";};
    };

    # Variant configurations are deliberately lazy and live outside `checks`.
    # Routine `nix flake check` therefore validates the real Singularity host and
    # cheap structural invariants without evaluating every alternate full system.
    # `nix run .#check-variants` evaluates these paths serially on demand.
    lib.workstation.variantDrvPaths =
      lib.mapAttrs
      (_: settingsOverride:
        (mkHost {
          host = "Singularity";
          inherit settingsOverride;
        }).config.system.build.toplevel.drvPath)
      supportedAlternativeOverrides;

    apps.x86_64-linux.check-variants = let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      variantNamesFile =
        pkgs.writeText "workstation-supported-variants"
        (lib.concatStringsSep "\n" supportedAlternativeNames + "\n");
      checkVariants = pkgs.writeShellApplication {
        name = "check-variants";
        runtimeInputs = [pkgs.git pkgs.nix];
        text = ''
          export WORKSTATION_VARIANTS_FILE=${variantNamesFile}
          ${builtins.readFile ./scripts/check-variants.sh}
        '';
      };
    in {
      type = "app";
      program = "${checkVariants}/bin/check-variants";
      meta.description = "Evaluate supported non-baseline workstation variants serially";
    };

    checks.x86_64-linux = let
      pkgs = nixpkgs.legacyPackages.x86_64-linux;
      policyConfig = self.nixosConfigurations.Singularity.config;
      policyUsername = policyConfig.workstation.user.name;
      policyGroups = builtins.sort builtins.lessThan policyConfig.users.users.${policyUsername}.extraGroups;
      expectedPolicyGroups = builtins.sort builtins.lessThan [
        "wheel"
        "input"
        "networkmanager"
        "video"
        "audio"
        "libvirtd"
        "kvm"
      ];
      firewallPublicServices = builtins.sort builtins.lessThan policyConfig.services.firewalld.zones.public.services;
      firewallHomeServices = builtins.sort builtins.lessThan policyConfig.services.firewalld.zones.home.services;
      expectedPublicServices = ["dhcpv6-client"];
      expectedHomeServices = builtins.sort builtins.lessThan [
        "dhcpv6-client"
        "kdeconnect"
      ];
      normalizeFirewallPorts = ports:
        builtins.sort builtins.lessThan (map (entry: "${toString entry.port}/${entry.protocol}") ports);
      firewallPublicPorts = normalizeFirewallPorts policyConfig.services.firewalld.zones.public.ports;
      firewallHomePorts = normalizeFirewallPorts policyConfig.services.firewalld.zones.home.ports;
      expectedPublicPorts = [];
      expectedHomePorts = builtins.sort builtins.lessThan [
        "21027/udp"
        "38459/tcp"
        "38459/udp"
        "443/tcp"
      ];
      ankiSyncHostname = policyConfig.workstation.network.ankiSyncHostname;
      ankiServiceConfig = policyConfig.systemd.services.anki-sync-server.serviceConfig;
      ankiServiceEnvironment = ankiServiceConfig.Environment;
      ankiLoadCredential = ankiServiceConfig.LoadCredential;
      ankiCaddyGlobalConfig = policyConfig.services.caddy.globalConfig;
      ankiCaddyConfig = policyConfig.services.caddy.virtualHosts.${ankiSyncHostname}.extraConfig;
      trustedConnectionUuids = policyConfig.workstation.network.trustedConnectionUuids;
    in {
      system = policyConfig.system.build.toplevel;

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
          if rg -n \
            -e 'hosts/.*/variables\.nix' \
            -e '\bworkstationSettings\b' \
            "$src/modules" --glob '*.nix'; then
            echo "ordinary modules must consume config.workstation; raw workstationSettings is host-only" >&2
            exit 1
          fi

          expected_selector_users="$(printf '%s\n' \
            modules/desktop/hyprland/default.nix \
            modules/desktop/hyprland/programs/waybar/default.nix)"
          actual_selector_users="$(
            rg -l '\bworkstationSelections\b' "$src/modules" --glob '*.nix' \
              | sed "s#^$src/##" \
              | sort
          )"
          if [ "$actual_selector_users" != "$expected_selector_users" ]; then
            echo "workstationSelections is an import-time escape hatch; its consumers must remain explicit" >&2
            echo "expected:" >&2
            printf '%s\n' "$expected_selector_users" >&2
            echo "actual:" >&2
            printf '%s\n' "$actual_selector_users" >&2
            exit 1
          fi
          touch "$out"
        '';

      installation-boundary =
        pkgs.runCommand "installation-boundary-check" {
          nativeBuildInputs = [pkgs.ripgrep];
          src = ./.;
        } ''
          reject_matches() {
            local message="$1"
            shift
            local output rc
            set +e
            output="$(rg -n "$@" 2>&1)"
            rc=$?
            set -e
            case "$rc" in
              0)
                printf '%s\n' "$output" >&2
                echo "$message" >&2
                exit 1
                ;;
              1) ;;
              *)
                printf '%s\n' "$output" >&2
                echo "installation-boundary scan failed: $message" >&2
                exit "$rc"
                ;;
            esac
          }

          reject_matches \
            "concrete installation identifiers/stateVersion/foreign boot entries must live under hosts/<name>/" \
            -e '/dev/disk/by-(uuid|partuuid|label|partlabel)/' \
            -e 'fileSystems\."/mnt/' \
            -e 'root=(UUID|PARTUUID|LABEL|PARTLABEL)=' \
            -e '\bsystem\.stateVersion[[:space:]]*=' \
            -e '\bboot\.loader\.grub\.extraEntries[[:space:]]*=' \
            -e 'device[[:space:]]*=[[:space:]]*"/swapfile"' \
            "$src/modules" --glob '*.nix'

          reject_matches \
            "generated hardware-configuration.nix must not own deliberate /mnt/* storage mounts" \
            -e 'fileSystems\."/mnt/' \
            "$src/hosts" --glob 'hardware-configuration.nix'

          reject_matches \
            "physical NetworkManager trust identifiers must not live in raw host selector variables" \
            -e '\btrustedConnectionUuids[[:space:]]*=' \
            "$src/hosts" --glob 'variables.nix'

          reject_matches \
            "generic flake policy must consume host-owned connection UUIDs, not duplicate literal lists" \
            -e 'ConnectionUuids[[:space:]]*=[[:space:]]*\[' \
            "$src/flake.nix"

          reject_matches \
            "Home Manager compatibility state must not live in reusable NixOS modules" \
            -e '\bhome\.stateVersion[[:space:]]*=' \
            -U -e 'home[[:space:]]*=[[:space:]]*\{[^}]*stateVersion[[:space:]]*=' \
            "$src/modules" --glob '*.nix'

          reject_matches \
            "core/users.nix must not own nested Home Manager installation state" \
            -e '^[[:space:]]*stateVersion[[:space:]]*=' \
            "$src/modules/core/users.nix"

          reject_matches \
            "reusable user modules must not own installation-specific home.stateVersion" \
            -e '\bhome\.stateVersion[[:space:]]*=' \
            -U -e 'home[[:space:]]*=[[:space:]]*\{[^}]*stateVersion[[:space:]]*=' \
            "$src/users" --glob '*.nix'

          if [ -d "$src/modules/hardware/drives" ]; then
            echo "concrete host storage must not live under modules/hardware/drives" >&2
            exit 1
          fi

          touch "$out"
        '';

      choice-catalog = assert choiceCatalogIsValid;
        pkgs.runCommand "workstation-choice-catalog-check" {} ''
          touch "$out"
        '';

      system-policy = assert policyConfig.system.stateVersion == "26.05";
      assert policyConfig.home-manager.users.${policyUsername}.home.stateVersion == "26.05";
      assert policyConfig.services.openssh.enable == false;
      assert policyConfig.users.users.${policyUsername}.initialPassword == null;
      assert policyGroups == expectedPolicyGroups;
      assert policyConfig.services.printing.enable == false;
      assert policyConfig.hardware.sane.enable == false;
      assert policyConfig.virtualisation.docker.enable == false;
      assert policyConfig.virtualisation.libvirtd.enable == true;
      assert policyConfig.programs.virt-manager.enable == true;
      assert policyConfig.services.qemuGuest.enable == false;
      assert policyConfig.services.spice-vdagentd.enable == false;
      assert policyConfig.services.spice-webdavd.enable == false;
      assert policyConfig.nix.settings.trusted-users == ["root"];
      assert policyConfig.nix.settings.allowed-users == [policyUsername];
      assert policyConfig.nix.settings.accept-flake-config == false;
      assert policyConfig.programs.nh.clean.enable == false;
        pkgs.runCommand "workstation-system-policy-check" {} ''
          touch "$out"
        '';

      firewall-policy = assert policyConfig.networking.firewall.enable == false;
      assert policyConfig.networking.nftables.enable == true;
      assert policyConfig.networking.nftables.flushRuleset == false;
      assert policyConfig.networking.nftables.ruleset == "";
      assert policyConfig.networking.nftables.rulesetFile == null;
      assert policyConfig.networking.nftables.tables == {};
      assert policyConfig.virtualisation.libvirtd.firewallBackend == "iptables";
      assert policyConfig.services.firewalld.enable == true;
      assert policyConfig.services.firewalld.settings.DefaultZone == "public";
      assert policyConfig.services.firewalld.settings.FirewallBackend == "nftables";
      assert policyConfig.services.firewalld.zones.public.forward == false;
      assert policyConfig.services.firewalld.zones.home.forward == false;
      assert policyConfig.services.firewalld.zones.public.masquerade == false;
      assert policyConfig.services.firewalld.zones.home.masquerade == false;
      assert policyConfig.services.firewalld.zones.public.interfaces == [];
      assert policyConfig.services.firewalld.zones.home.interfaces == [];
      assert policyConfig.services.firewalld.zones.public.sources == [];
      assert policyConfig.services.firewalld.zones.home.sources == [];
      assert policyConfig.services.firewalld.zones.public.protocols == [];
      assert policyConfig.services.firewalld.zones.home.protocols == [];
      assert policyConfig.services.firewalld.zones.public.sourcePorts == [];
      assert policyConfig.services.firewalld.zones.home.sourcePorts == [];
      assert policyConfig.services.firewalld.zones.public.forwardPorts == [];
      assert policyConfig.services.firewalld.zones.home.forwardPorts == [];
      assert policyConfig.services.firewalld.zones.public.rules == [];
      assert policyConfig.services.firewalld.zones.home.rules == [];
      assert trustedConnectionUuids != [];
      assert firewallPublicServices == expectedPublicServices;
      assert firewallHomeServices == expectedHomeServices;
      assert firewallPublicPorts == expectedPublicPorts;
      assert firewallHomePorts == expectedHomePorts;
      assert policyConfig.services.adguardhome.enable == false;
      assert policyConfig.services.unbound.enable == false;
      assert policyConfig.services.minidlna.enable == false;
      assert policyConfig.services.syncthing.openDefaultPorts == false;
      assert !(builtins.hasAttr "syncthing-init" policyConfig.systemd.services);
      assert policyConfig.programs.steam.remotePlay.openFirewall == false;
      assert policyConfig.programs.steam.dedicatedServer.openFirewall == false;
      assert policyConfig.programs.steam.localNetworkGameTransfers.openFirewall == false;
        pkgs.runCommand "workstation-firewall-policy-check" {} ''
          touch "$out"
        '';

      anki-sync-policy = assert ankiSyncHostname != "";
      assert policyConfig.services.caddy.enable == true;
      assert builtins.elem "PASSWORDS_HASHED=1" ankiServiceEnvironment;
      assert builtins.elem "SYNC_HOST=127.0.0.1" ankiServiceEnvironment;
      assert builtins.elem "SYNC_PORT=27701" ankiServiceEnvironment;
      assert lib.all (entry: !(lib.hasPrefix "SYNC_USER" entry)) ankiServiceEnvironment;
      assert builtins.elem "MAX_SYNC_PAYLOAD_MEGS=1000000" ankiServiceEnvironment;
      assert ankiLoadCredential == ["anki-sync-password-hash:/var/lib/anki-sync-server-credentials/password.phc"];
      assert lib.hasInfix "auto_https disable_redirects" ankiCaddyGlobalConfig;
      assert !(lib.hasInfix "default_bind" ankiCaddyGlobalConfig);
      assert lib.hasInfix "servers :443" ankiCaddyGlobalConfig;
      assert lib.hasInfix "protocols h1 h2" ankiCaddyGlobalConfig;
      assert lib.hasInfix "disable_http_challenge" ankiCaddyConfig;
      assert lib.hasInfix "request_body" ankiCaddyConfig;
      assert lib.hasInfix "max_size 1GB" ankiCaddyConfig;
      assert lib.hasInfix "127.0.0.1:27701" ankiCaddyConfig;
      assert lib.hasInfix "read_buffer 512k" ankiCaddyConfig;
      assert ankiServiceConfig.NoNewPrivileges == true;
      assert ankiServiceConfig.PrivateTmp == true;
      assert ankiServiceConfig.PrivateDevices == true;
      assert ankiServiceConfig.ProtectClock == true;
      assert ankiServiceConfig.ProtectControlGroups == true;
      assert ankiServiceConfig.ProtectKernelLogs == true;
      assert ankiServiceConfig.ProtectKernelModules == true;
      assert ankiServiceConfig.ProtectKernelTunables == true;
      assert ankiServiceConfig.LockPersonality == true;
      assert ankiServiceConfig.RestrictRealtime == true;
      assert ankiServiceConfig.RestrictSUIDSGID == true;
      assert toString ankiServiceConfig.CapabilityBoundingSet == "";
      assert toString ankiServiceConfig.UMask == "0077";
      assert toString ankiServiceConfig.TasksMax == "256";
      assert toString ankiServiceConfig.MemoryHigh == "3G";
      assert toString ankiServiceConfig.MemoryMax == "4G";
      assert toString ankiServiceConfig.MemorySwapMax == "1G";
      assert !(builtins.elem 27701 policyConfig.networking.firewall.allowedTCPPorts);
        pkgs.runCommand "workstation-anki-sync-policy-check" {} ''
          touch "$out"
        '';

      dns-policy = assert policyConfig.services.resolved.enable == false;
      assert policyConfig.services.adguardhome.enable == false;
      assert policyConfig.services.unbound.enable == false;
      assert policyConfig.networking.networkmanager.dns == "default";
      assert policyConfig.networking.networkmanager.insertNameservers == [];
      assert policyConfig.networking.networkmanager.appendNameservers == [];
      assert policyConfig.networking.nameservers == [];
      assert policyConfig.networking.resolvconf.enable == true;
        pkgs.runCommand "workstation-dns-policy-check" {} ''
          touch "$out"
        '';

      cleanup-policy = assert policyConfig.services.scx.enable == false;
      assert policyConfig.services.minidlna.enable == false;
      assert policyConfig.services.tlp.enable == true;
      assert policyConfig.services.devmon.enable == true;
      assert policyConfig.services.gvfs.enable == true;
      assert policyConfig.services.udisks2.enable == true;
      assert policyConfig.services.pipewire.jack.enable == false;
      assert policyConfig.programs.fuse.userAllowOther == false;
      assert policyConfig.programs.mtr.enable == false;
      assert !(builtins.hasAttr "mtr-packet" policyConfig.security.wrappers);
      assert policyConfig.programs.gamemode.enable == true;
      assert policyConfig.programs.gamemode.enableRenice == false;
      assert !(builtins.hasAttr "gamemoded" policyConfig.security.wrappers);
      assert policyConfig.programs.gamescope.capSysNice == true;
      assert policyConfig.programs.gnupg.agent.enable == true;
      assert policyConfig.programs.gnupg.agent.enableSSHSupport == true;
      assert policyConfig.hardware.keyboard.qmk.enable == true;
      assert !(builtins.hasAttr "Experimental" policyConfig.hardware.bluetooth.settings.General);
      assert !(builtins.hasAttr "KernelExperimental" policyConfig.hardware.bluetooth.settings.General);
      assert !(builtins.hasAttr "FastConnectable" policyConfig.hardware.bluetooth.settings.General);
      assert !(builtins.hasAttr "JustWorksRepairing" policyConfig.hardware.bluetooth.settings.General);
      assert !(builtins.hasAttr "GATT" policyConfig.hardware.bluetooth.settings);
      assert !(builtins.hasAttr "Policy" policyConfig.hardware.bluetooth.settings);
      assert policyConfig.programs.thunar.enable == true;
      assert policyConfig.services.tlp.settings.START_CHARGE_THRESH_BAT0 == 90;
      assert policyConfig.services.tlp.settings.STOP_CHARGE_THRESH_BAT0 == 95;
      assert !(builtins.hasAttr "START_CHARGE_THRESH_BAT1" policyConfig.services.tlp.settings);
      assert !(builtins.hasAttr "STOP_CHARGE_THRESH_BAT1" policyConfig.services.tlp.settings);
      assert (policyConfig.nix.settings."download-buffer-size" or null) != 200000000;
      assert policyConfig.nix.settings.auto-optimise-store == false;
      assert !(builtins.elem "ventoy-1.1.12" (policyConfig.nixpkgs.config.permittedInsecurePackages or []));
      assert policyConfig.nix.optimise.automatic == true;
      assert !(builtins.hasAttr "lactd" policyConfig.systemd.services);
      assert !(builtins.elem "tcp_bbr" policyConfig.boot.kernelModules);
      assert !(builtins.hasAttr "net.ipv4.tcp_congestion_control" policyConfig.boot.kernel.sysctl);
      assert !(builtins.hasAttr "net.ipv4.tcp_rfc1337" policyConfig.boot.kernel.sysctl);
      assert policyConfig.boot.kernel.sysctl."net.core.bpf_jit_enable" == 1;
      assert policyConfig.boot.kernel.sysctl."net.core.bpf_jit_harden" == 2;
      assert !(builtins.hasAttr "net.core.bpf_jit_kallsyms" policyConfig.boot.kernel.sysctl);
        pkgs.runCommand "workstation-cleanup-policy-check" {} ''
          touch "$out"
        '';
    };

    devShells = forAllToolSystems (system: let
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
