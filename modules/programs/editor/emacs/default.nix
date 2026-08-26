{pkgs, ...}: {
  home-manager.sharedModules = [
    (_: {
      programs.emacs = {
        enable = true;
        package = pkgs.emacs-pgtk;
      };

      # Home Manager defaults this to programs.emacs.finalPackage when Emacs
      # is enabled, so the daemon and interactive package stay identical.
      services.emacs.enable = true;
    })
  ];
}
