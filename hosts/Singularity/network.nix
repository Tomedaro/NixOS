{...}: {
  # Existing NetworkManager profiles remain externally managed. This UUID is
  # specific to Singularity and is assigned to the firewalld home zone at
  # runtime without persisting a zone change into the connection profile.
  workstation.network.trustedConnectionUuids = [
    "c7d1f765-e254-4a6f-ab29-21ec5a9f49e1" # Bbox-93F30CDB
  ];
}
