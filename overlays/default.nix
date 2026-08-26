{inputs, ...}: {
  default = final: prev:
    (import ../pkgs {pkgs = final;})
    // {
      vesktop = prev.vesktop.override {
        withSystemVencord = false;
        withMiddleClickScroll = true;
      };
      discord = prev.discord.override {
        withVencord = true;
        withOpenASAR = true;
        enableAutoscroll = true;
      };
      lact = prev.lact.overrideAttrs (old: {
        postPatch =
          (old.postPatch or "")
          + ''
            # libdisplay-info 0.4.0 breaks the vendored libdisplay-info-sys 0.3.0 version constraint.
            # Keep this compatibility patch only while the pinned package still needs it.
            sed -i 's|< 0.4.0|< 0.5.0|g' "$cargoDepsCopy/source-registry-0/libdisplay-info-sys-0.3.0/Cargo.toml"
          '';
      });
    };
}
