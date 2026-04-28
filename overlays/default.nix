{ host, inputs, ... }:
let
  inherit (import ../hosts/${host}/variables.nix) sddmTheme;
in
{
  additions =
    final: _prev:
    import ../pkgs {
      pkgs = final;
      inherit host;
    };

  modifications = final: prev: {
    nur = inputs.nur.overlays.default;
    stable = import inputs.nixpkgs-stable {
      system = final.stdenv.hostPlatform.system;
      config.allowUnfree = true;
    };
    vesktop = prev.vesktop.override {
      withSystemVencord = false;
      withMiddleClickScroll = true;
    };
    discord = prev.discord.override {
      withVencord = true;
      withOpenASAR = true;
      enableAutoscroll = true;
    };
    hyprland = prev.hyprland.overrideAttrs (old: {
      postPatch = (old.postPatch or "") + ''
        # Accept undersized shm fds from libwayshot (screenpipe resets fd size on retry)
        for f in $(grep -rl "st_size >= size" src/ 2>/dev/null); do
          substituteInPlace "$f" \
            --replace 'return (size_t)st.st_size >= size;' \
            'if ((size_t)st.st_size < (size_t)size) ftruncate(fd, size); return 1;'
        done
      '';
    });
  };
}
