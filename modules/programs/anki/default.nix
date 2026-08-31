# ~/NixOS/modules/programs/anki/default.nix
{
  config,
  pkgs,
  ...
}: let
  serviceUser = config.workstation.user.name;
  syncHostname = config.workstation.network.ankiSyncHostname;
  syncAccount = "Daniil";
  credentialFile = "/var/lib/anki-sync-server-credentials/password.phc";
  startServer = pkgs.writeShellScript "anki-sync-server-start" ''
    set -eu

    passwordHash="$(${pkgs.coreutils}/bin/cat "$CREDENTIALS_DIRECTORY/anki-sync-password-hash")"
    case "$passwordHash" in
      '$pbkdf2-sha256$'*) ;;
      *)
        echo "Anki sync credential is not a PBKDF2-SHA256 PHC hash" >&2
        exit 1
        ;;
    esac

    export SYNC_USER1="${syncAccount}:$passwordHash"
    exec ${pkgs.anki-sync-server}/bin/anki-sync-server
  '';
in {
  environment.systemPackages = [pkgs.anki-sync-server];

  # Keep only the password hash outside the Nix store. The migration runner
  # installs it root-only before activation; systemd exposes a private
  # credential copy to the unprivileged Anki service at runtime.
  systemd.tmpfiles.rules = [
    "d /var/lib/anki-sync-server-credentials 0700 root root -"
  ];

  services.caddy = {
    enable = true;

    # Use Caddy's standard TCP/443 listener. Avoid `default_bind` here:
    # Caddy 2.11 maps it into the ACME challenge bind host; keeping the
    # standard listener avoids coupling HTTP listener syntax to ACME binding.
    # HTTP/3 is unnecessary for Anki and would add a UDP/443 listener.
    globalConfig = ''
      auto_https disable_redirects

      servers :443 {
        protocols h1 h2
      }
    '';

    virtualHosts."${syncHostname}".extraConfig = ''
      tls {
        issuer acme {
          disable_http_challenge
        }
      }

      # Keep Anki's intentionally huge internal override, but do not expose a
      # near-unbounded pre-authentication request envelope to the Internet.
      # The audited collection is ~421 MiB; 1 GB gives substantial headroom.
      request_body {
        max_size 1GB
      }

      reverse_proxy http://127.0.0.1:27701 {
        transport http {
          read_buffer 512k
        }
      }
    '';
  };

  systemd.services.anki-sync-server = {
    description = "Anki Sync Server";
    after = ["network.target"];
    wantedBy = ["multi-user.target"];
    serviceConfig = {
      Environment = [
        "PASSWORDS_HASHED=1"
        # Intentionally retained for this unusually large self-hosted
        # collection. This value is MiB, not bytes.
        "MAX_SYNC_PAYLOAD_MEGS=1000000"
        "SYNC_HOST=127.0.0.1"
        "SYNC_PORT=27701"
      ];
      LoadCredential = ["anki-sync-password-hash:${credentialFile}"];
      User = serviceUser;
      Group = "users";
      ExecStart = startServer;
      Restart = "on-failure";
      RestartSec = "5s";

      # Low-risk containment that does not move or remount the existing
      # ~/.syncserver state. Filesystem privilege isolation is deferred to a
      # separate state-migration tranche.
      NoNewPrivileges = true;
      PrivateTmp = true;
      PrivateDevices = true;
      ProtectClock = true;
      ProtectControlGroups = true;
      ProtectKernelLogs = true;
      ProtectKernelModules = true;
      ProtectKernelTunables = true;
      LockPersonality = true;
      RestrictRealtime = true;
      RestrictSUIDSGID = true;
      CapabilityBoundingSet = "";
      UMask = "0077";
      TasksMax = 256;

      # The host has ~15.3 GiB RAM and the service normally peaks at ~59 MiB.
      # Combined with Caddy's 1 GB request cap, these bounds contain malformed
      # or hostile decompression without constraining the audited collection.
      MemoryHigh = "3G";
      MemoryMax = "4G";
      MemorySwapMax = "1G";
    };
  };
}
