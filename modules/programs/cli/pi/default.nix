{mkMcpNixos}: {
  _class = "homeManager";
  imports = [
    (import ./home-module.nix {inherit mkMcpNixos;})
  ];
}
