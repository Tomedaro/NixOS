{
  pkgs,
  lib,
  ...
<<<<<<< HEAD
}: let
  inherit (lib) getExe';
in
  pkgs.writeShellScriptBin "driverinfo" ''
    ${getExe' pkgs.vulkan-tools "vulkaninfo"} | grep -i "deviceName\|driverID"
  ''
=======
}:
let
  inherit (lib) getExe';
in
pkgs.writeShellScriptBin "driverinfo" ''
  ${getExe' pkgs.vulkan-tools "vulkaninfo"} | grep -i "deviceName\|driverID"
''
>>>>>>> upstream/master
