{
  config,
  lib,
  pkgs,
  ...
}: let
  hostname = config.workstation.hostName;
  trustedConnectionUuids = config.workstation.network.trustedConnectionUuids;
  nmcli = "${pkgs.networkmanager}/bin/nmcli";
  zoneStateDir = "/run/workstation-network-zones";
  restoreTrustedZones = pkgs.writeShellScript "workstation-network-zones-restore" ''
    set +e
    ${lib.concatMapStringsSep "\n" (uuid: let
        stateFile = "${zoneStateDir}/${uuid}.zone";
      in ''
        if [ -f ${lib.escapeShellArg stateFile} ] \
          && ${nmcli} connection show uuid ${lib.escapeShellArg uuid} >/dev/null 2>&1; then
          previous_zone="$(${pkgs.coreutils}/bin/cat ${lib.escapeShellArg stateFile})"
          ${nmcli} connection modify --temporary uuid ${lib.escapeShellArg uuid} connection.zone "$previous_zone"
        fi
        ${pkgs.coreutils}/bin/rm -f ${lib.escapeShellArg stateFile}
      '')
      trustedConnectionUuids}
  '';
  applyTrustedZones = pkgs.writeShellScript "workstation-network-zones-apply" ''
    set -eu
    rollback() {
      ${restoreTrustedZones}
    }
    trap rollback EXIT
    trap 'exit 1' HUP INT TERM

    ${lib.concatMapStringsSep "\n" (uuid: let
        stateFile = "${zoneStateDir}/${uuid}.zone";
      in ''
        ${nmcli} connection show uuid ${lib.escapeShellArg uuid} >/dev/null
        previous_zone="$(${nmcli} -g connection.zone connection show uuid ${lib.escapeShellArg uuid})"
        printf '%s' "$previous_zone" > ${lib.escapeShellArg stateFile}
        ${nmcli} connection modify --temporary uuid ${lib.escapeShellArg uuid} connection.zone home
      '')
      trustedConnectionUuids}

    trap - EXIT HUP INT TERM
  '';
in {
  networking = {
    hostName = "${hostname}";
    networkmanager = {
      enable = true;
      # Keep global DNS injection empty. The active connection owns DNS.
      insertNameservers = [];
    };

    # Firewall policy belongs to standalone firewalld. NixOS still requires
    # nftables support to be enabled for firewalld's nftables backend; keep
    # the NixOS nftables ruleset empty and never let it flush other owners.
    firewall.enable = false;
    nftables = {
      enable = true;
      flushRuleset = false;
      ruleset = "";
      rulesetFile = null;
      tables = {};
    };
  };

  services.firewalld = {
    enable = true;
    settings = {
      DefaultZone = "public";
      FirewallBackend = "nftables";
    };

    # /etc/firewalld zone definitions override the packaged defaults. Keep
    # the lists explicit so adding a service elsewhere cannot silently expose
    # it on every network. The Anki sync server uses plaintext HTTP, so its
    # port is restricted to the explicitly trusted home zone.
    zones = {
      public = {
        services = ["dhcpv6-client"];
        ports = [];
      };

      home = {
        services = [
          "dhcpv6-client"
          "kdeconnect"
        ];
        # Syncthing's persistent user config currently listens on 38459. Keep
        # the firewall aligned without taking declarative ownership of its
        # manually managed devices, folders, or other Syncthing settings.
        ports = [
          {
            port = 27701;
            protocol = "tcp";
          }
          {
            port = 38459;
            protocol = "tcp";
          }
          {
            port = 38459;
            protocol = "udp";
          }
          {
            port = 21027;
            protocol = "udp";
          }
        ];
      };
    };
  };

  boot.kernel.sysctl = {
    # Keep explicit security policy; rely on current kernel defaults for TCP
    # congestion control, buffers, pacing, ECN and latency behavior.
    "kernel.sysrq" = 0;
    "net.ipv4.conf.default.rp_filter" = 1;
    "net.ipv4.conf.all.rp_filter" = 1;
    "net.ipv4.conf.default.send_redirects" = 0;
    "net.ipv4.conf.all.send_redirects" = 0;
    "net.ipv4.conf.default.accept_redirects" = 0;
    "net.ipv4.conf.all.accept_redirects" = 0;
    "net.ipv4.conf.default.secure_redirects" = 0;
    "net.ipv4.conf.all.secure_redirects" = 0;
    "net.ipv6.conf.default.accept_redirects" = 0;
    "net.ipv6.conf.all.accept_redirects" = 0;
    "net.ipv4.tcp_syncookies" = 1;

    "kernel.kptr_restrict" = 2;
    "kernel.dmesg_restrict" = 1;
    "kernel.printk" = "3 3 3 3";
    "kernel.unprivileged_bpf_disabled" = 1;
    "kernel.yama.ptrace_scope" = 1;
    # Keep BPF JIT explicitly enabled and hardened; only the incompatible
    # kallsyms-export override is removed.
    "net.core.bpf_jit_enable" = 1;
    "net.core.bpf_jit_harden" = 2;
  };

  # Assign only explicitly trusted existing NetworkManager profiles to the
  # home zone. --temporary keeps credentials/profile ownership out of Nix and
  # ExecStop makes `switch-to-configuration test` rollback-clean. NetworkManager
  # immediately reapplies connection.zone to an already-active interface.
  systemd.services.workstation-network-zones = lib.mkIf (trustedConnectionUuids != []) {
    description = "Assign trusted NetworkManager connections to firewalld home zone";
    requires = [
      "NetworkManager.service"
      "firewalld.service"
    ];
    after = [
      "NetworkManager.service"
      "firewalld.service"
    ];
    partOf = ["NetworkManager.service"];
    wantedBy = ["multi-user.target"];
    serviceConfig = {
      Type = "oneshot";
      RemainAfterExit = true;
      RuntimeDirectory = "workstation-network-zones";
      RuntimeDirectoryMode = "0700";
      ExecStart = applyTrustedZones;
      ExecStop = restoreTrustedZones;
    };
  };

  systemd.services.NetworkManager-wait-online.enable = false;
  systemd.network.wait-online.enable = false;

  environment.systemPackages = with pkgs; [networkmanagerapplet];
}
