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
    networkmanager.enable = true;
    # DNS migration is deliberately deferred to the next tranche.
    networkmanager.insertNameservers = ["1.1.1.1" "1.0.0.1"];

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
    # it on every network. Anki/27701 is the intentionally retained exception.
    zones = {
      public = {
        services = ["dhcpv6-client"];
        ports = [
          {
            port = 27701;
            protocol = "tcp";
          }
        ];
      };

      home = {
        services = [
          "dhcpv6-client"
          "kdeconnect"
        ];
        ports = [
          {
            port = 27701;
            protocol = "tcp";
          }
          {
            port = 8200;
            protocol = "tcp";
          }
          {
            port = 1900;
            protocol = "udp";
          }
          {
            port = 22000;
            protocol = "tcp";
          }
          {
            port = 22000;
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

  boot = {
    kernelModules = ["tcp_bbr"];
    kernel.sysctl = {
      # TCP hardening
      "kernel.sysrq" = 0;
      "net.ipv4.conf.default.rp_filter" = 1;
      "net.ipv4.conf.all.rp_filter" = 1;
      "net.ipv4.conf.default.send_redirects" = 0;
      "net.ipv4.conf.default.accept_redirects" = 0;
      "net.ipv4.conf.all.secure_redirects" = 0;
      "net.ipv4.conf.default.secure_redirects" = 0;
      "net.ipv6.conf.all.accept_redirects" = 0;
      "net.ipv6.conf.default.accept_redirects" = 0;
      "net.ipv4.tcp_syncookies" = 1;
      "net.ipv4.tcp_rfc1337" = 1;

      # BBR + ECN optimization (Kernel 6.x)
      "net.ipv4.tcp_congestion_control" = "bbr";
      "net.ipv4.tcp_ecn" = 1;
      "net.ipv4.tcp_ecn_fallback" = 1;

      # TCP ultra low latency
      "net.ipv4.tcp_fastopen" = 3;
      "net.ipv4.tcp_fin_timeout" = 30;
      "net.ipv4.tcp_window_scaling" = 1;
      "net.ipv4.tcp_mtu_probing" = 1;
      "net.ipv4.tcp_slow_start_after_idle" = 0;
      "net.ipv4.tcp_notsent_lowat" = 16384;

      # BBR pacing (Kernel 6.x)
      "net.ipv4.tcp_pacing_ss_ratio" = 200;
      "net.ipv4.tcp_pacing_ca_ratio" = 120;

      # Buffer optimization (1Gbps Optimized)
      "net.ipv4.tcp_rmem" = "4096 131072 67108864";
      "net.ipv4.tcp_wmem" = "4096 65536 67108864";
      "net.core.wmem_max" = 67108864;
      "net.core.rmem_max" = 67108864;
      "net.core.wmem_default" = 1048576;
      "net.core.rmem_default" = 1048576;

      # Queue management
      "net.core.default_qdisc" = "fq";
      "net.core.netdev_max_backlog" = 16384;
      "net.core.somaxconn" = 2048;

      # Netdev budget
      "net.core.netdev_budget" = 600;
      "net.core.netdev_budget_usecs" = 8000;

      # Kernel Security Hardening
      "kernel.kptr_restrict" = 2;
      "kernel.dmesg_restrict" = 1;
      "kernel.printk" = "3 3 3 3";
      "kernel.unprivileged_bpf_disabled" = 1;
      "kernel.yama.ptrace_scope" = 1;

      # BPF JIT compiler (performance boost & hardening)
      "net.core.bpf_jit_enable" = 1;
      "net.core.bpf_jit_harden" = 2;
      "net.core.bpf_jit_kallsyms" = 1;

      # IPv6
      "net.ipv6.conf.all.accept_ra" = 1;
    };
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
