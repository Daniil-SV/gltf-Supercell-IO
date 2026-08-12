<div align="center">

# glTF Supercell IO

**Custom Blender Extension for Supercell Odin glTF (.glb) Import & Export**

[![Blender 5.2+](https://img.shields.io/badge/Blender-5.2%2B-orange.svg?logo=blender)](https://www.blender.org/)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![GitHub release](https://img.shields.io/github/v/release/Daniil-SV/gltf-Supercell-IO?color=brightgreen)](https://github.com/Daniil-SV/gltf-Supercell-IO/releases)

---

A reimagined, modern successor to **Flat Converter** — fully integrated into Blender's native glTF 2.0 pipeline.

[Key Features](#key-features) • [Demo](#demo) • [Requirements](#requirements) • [Installation](#installation) • [Usage](#usage) • [Debugging](#debugging)

</div>

---

> [!IMPORTANT]
> **Supercell Fan Content Policy**  
> This material is unofficial and is not endorsed by Supercell. For more information see Supercell's Fan Content Policy: [www.supercell.com/fan-content-policy](https://www.supercell.com/fan-content-policy).

---

## Overview

**gltf-Supercell-IO** is a dedicated Blender extension that enhances the official Khronos Group glTF 2.0 importer/exporter with support for **Supercell's custom Odin `.glb` format** (used in games like Brawl Stars, Clash Royale, and others).

Instead of relying on external command-line tools or multi-step converters, this plugin integrates directly into Blender 5.2+, allowing you to import, edit, rig, and export Supercell 3D models with a single click.

---

## Demo

<div align="center">

[![glTF IO Demo video](https://thumbs.video-to-markdown.com/0f5d1cd0.jpg)](https://youtu.be/GEk-9UhVXgM)

</div>

</details>

---

## Key Features

- **Seamless Integration:** Hooks into Blender's built-in glTF 2.0 system — no extra UI clutter or detached tools.
- **Built-in Image Processing:** Integrated image converter for handling custom texture decodings automatically.
- **Neko API Integration:** Fetch and convert textures on-the-fly using the integrated Neko API.
- **Skinning & Armatures:** Proper parsing of skin joints, custom bone hierarchies.

---

## Requirements

- **Blender 5.2+** is required due to updated extension API support
---

## Installation

1. Go to the **[Releases](https://github.com/Daniil-SV/gltf-Supercell-IO/releases)** section and download the latest `.zip` package.
2. Launch **Blender 5.2+**.
3. Navigate to **Edit** ➔ **Preferences** (or press `Ctrl` + `,`).
4. Select the **Add-ons** / **Get Extensions** tab.
5. Click the top-right menu icon (⚙️ or dropdown arrow) and select **Install from Disk...**.
6. Choose the downloaded `.zip` file and activate the plugin.

---

## Usage

### Importing Supercell Assets
1. Go to **File** ➔ **Import** ➔ **glTF 2.0 (.glb / .gltf)**.
2. Choose your Supercell `.glb` file.
3. The plugin will automatically detect Supercell files, process textures, and set up the armature and materials.

### Exporting
1. Go to **File** ➔ **Export** ➔ **glTF 2.0 (.glb / .gltf)**.
3. Export your modified mesh or animations.

---

## Debugging

- [Debug with VSCode](https://github.com/KhronosGroup/glTF-Blender-IO/blob/main/DEBUGGING.md)

---