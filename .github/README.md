<h1 align="center">
   <img src="assets/nixos-logo.png" width="100px" /> 
   <br>
      My NixOS Configuration
   <br>
      <img src="https://raw.githubusercontent.com/catppuccin/catppuccin/main/assets/palette/macchiato.png" width="600px" /> <br>
   <div align="center">

   <div align="center">
      <p></p>
      <div align="center">
         <a href="https://github.com/Sly-Harvey/NixOS/stargazers">
            <img src="https://img.shields.io/github/stars/Sly-Harvey/NixOS?color=F5BDE6&labelColor=303446&style=for-the-badge&logo=starship&logoColor=F5BDE6">
         </a>
         <a href="https://github.com/Sly-Harvey/NixOS/network/members">
            <img src="https://img.shields.io/github/forks/Sly-Harvey/NixOS?color=C6A0F6&labelColor=303446&style=for-the-badge&logo=git&logoColor=C6A0F6" alt="GitHub Forks">
         </a>
         <!-- <a href="https://github.com/Sly-Harvey/NixOS/"> -->
         <!--    <img src="https://img.shields.io/github/repo-size/Sly-Harvey/NixOS?color=C6A0F6&labelColor=303446&style=for-the-badge&logo=github&logoColor=C6A0F6"> -->
         <!-- </a> -->
         <a = href="https://nixos.org">
            <img src="https://img.shields.io/badge/NixOS-Unstable-blue?style=for-the-badge&logo=NixOS&logoColor=91D7E3&label=NixOS&labelColor=303446&color=91D7E3">
            <!-- <img src="https://img.shields.io/badge/NixOS-unstable-blue.svg?style=for-the-badge&labelColor=303446&logo=NixOS&logoColor=white&color=91D7E3"> -->
         </a>
         <a href="https://github.com/Sly-Harvey/NixOS/blob/main/LICENSE">
            <img src="https://img.shields.io/static/v1.svg?style=for-the-badge&label=License&message=MIT&colorA=313244&colorB=F5A97F&logo=unlicense&logoColor=F5A97F&"/>
         </a>
      </div>
      <br>
   </div>
</h1>

## Screenshots

![Screenshot](assets/preview1.png)
![Screenshot](assets/preview2.png)

<details>
<summary>More screenshots</summary>

![Screenshot](assets/preview3.png)
![Screenshot](assets/preview4.png)
![Screenshot](assets/preview5.png)

</details>

## Table of Contents

- [Installation](#installation)
  <!-- - [Before You Begin](#before-you-begin) -->
  <!-- - [Installation Steps](#installation-steps) -->
- [Usage](#usage)
  - [Managing Hosts](#managing-hosts)
  - [Rebuilding](#rebuilding)
  - [Rollbacks](#rollbacks)
  - [Keybindings](#keybindings)
- [Development Shells](#development-shells)
- [Credits](#creditsinspiration)

## Installation

This repository currently has one concrete NixOS host: **Singularity**.

The old `install.sh` / `live-install.sh` workflow has been retired because it
created new machines by copying an existing host directory, which could carry
disk UUIDs, hardware configuration, tuning, and other installation-specific
state onto unrelated hardware.

For the current machine, the canonical configuration is:

```text
nixosConfigurations.Singularity
hosts/Singularity/
networking.hostName = "Singularity"
```

For a reinstall or a future second machine, see
[`docs/host-onboarding.md`](../docs/host-onboarding.md). Do **not** create a new
host by copying `hosts/Singularity`. New hardware must get its own generated
hardware configuration and explicit machine-specific storage/network facts.

## Usage

### Managing Hosts

`Singularity` is currently the only registered real host. Additional machines
will be added as explicit `nixosConfigurations.<HostName>` entries after their
own hardware/install facts are created. Support variants such as alternate
editors/desktops are tests, not additional hosts.

### Rebuilding

Apply configuration changes:

- **Keyboard shortcut:** `Super + U`
- **rebuild script:** `rebuild`
- **nixos-rebuild:** `sudo nixos-rebuild switch --flake ~/NixOS#<HOST>`
- **nh (current host; `NH_FLAKE` is configured):** `nh os switch`
- **nh (explicit host):** `nh os switch -H <HOST>`

For this machine, use `Singularity`. When additional real hosts are registered, use their canonical configuration names.

### Rollbacks

List generations:

```bash
list-gens
```

Rollback to generation N:

```bash
rollback N
```

Replace `N` with the generation number (e.g., `69`).

### Keybindings

View all keybindings with `Super + ?` or `Super + Ctrl + K`.

## Development Shells

Pre-configured dev shells for various languages are included.

Initialize a project from a template:

```bash
nix flake init -t ~/NixOS#<TEMPLATE_NAME>
```

Create a new project directory:

```bash
nix flake new -t ~/NixOS#<TEMPLATE_NAME> <PROJECT_NAME>
```

Templates are defined in `dev-shells/default.nix` (python, node, etc.).

Enter the shell:

```bash
cd <PROJECT_NAME>
nix develop
```

If you're using direnv, the shell activates automatically.

## Credits/Inspiration

| Credit                                                        | Reason                       |
| ------------------------------------------------------------- | ---------------------------- |
| [Hyprland-Dots](https://github.com/JaKooLit/Hyprland-Dots)    | Scripts and Waybar templates |
| [HyDE](https://github.com/HyDE-Project/HyDE)                  | Additional scripts           |
| [rofi](https://github.com/adi1090x/rofi)                      | Rofi launcher styles         |
| [dev-templates](https://github.com/the-nix-way/dev-templates) | Development templates        |
| [Vimjoyer](https://www.youtube.com/@vimjoyer)                 | NixOS tutorials              |

<!-- ---

## ⭐ Star History

<details>
<summary>View Star History</summary>

<a href="https://github.com/Sly-Harvey/NixOS/stargazers">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/svg?repos=Sly-Harvey/NixOS&type=Date&theme=dark" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/svg?repos=Sly-Harvey/NixOS&type=Date" />
   <img alt="Star History Chart" src="https://api.star-history.com/svg?repos=Sly-Harvey/NixOS&type=Date" />
 </picture>
</a>

</details> -->
