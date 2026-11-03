# GatewayTech — Lunar Gateway parts for KSP (This is vibecoded beware)

thanks to benjee10 for references & the-dev-hole 

Kerbal Space Program 1.12.x parts for building NASA's Lunar Gateway station, in the style and scale of Benjee10's HabTech2. Every module is a separate part. Solar wings roll out, antennas and radiators deploy, and both robotic arms unfold. The docking-port spots are recessed seats that take HabTech-family NDS docking ports.

(I needed gateway modules for a project so I took the easy route, expect rough models, issues, etc)

## Parts

| Part | Real module |
|---|---|
| GT-1 "Helios" Power & Propulsion Element | Gateway PPE (Maxar). Ion engine, probe core, SAS, folding dish antennas, two solar-wing mounts. |
| GT-1W "Helios" Roll-Out Solar Wing | PPE roll-out solar array (ROSA) wing. Sun-tracking, retractable. |
| GT-2 "Halo" Habitation & Logistics Outpost | HALO (Northrop Grumman). Command and control hub, main batteries, two dish antennas, 3 docking seats. |
| GT-3 "Hestia" International Habitation Module | I-Hab (ESA / Thales Alenia Space / JAXA). Crew 3, 4 docking seats, accordion radiators. |
| GT-4 "Iris" Refuelling Module | ESPRIT Refuelling Module (ESA / Thales Alenia Space). Xenon and monopropellant, viewing windows. |
| GT-5 "Portal" Crew & Science Airlock | Emirates Airlock (MBRSC / Thales Alenia Space). EVA airlock, accordion radiators. |
| GT-R1 "Long Reach" Station Arm | Canadarm3 large arm (MDA / CSA). Unfold/stow animation. |
| GT-R2 "Fingertip" Dexterous Arm | Canadarm3 small dexterous arm (MDA / CSA). Extend/stow animation. |

- **Scale:** 0.585× real size, matching HabTech2. I-Hab is 2.5 m across.
- **Mass:** 0.25× real (dry), the same ratio HabTech2 uses for its ISS modules.
- **Fuel:** propellant loads are scaled the same way.

## Requirements

- KSP 1.12.x
- **HabTech2** by Benjee10. The crewed modules use its IVAs.
- **Benjee10_sharedAssets** (recommended). Its `B10_NDS` / `B10_NDS_passive` ports sit exactly in GatewayTech's recessed seats.

## Installation

Copy `GameData/GatewayTech` from the release zip into your KSP `GameData` folder.

## Tips

- Docking ports go on each seat's stack node, not surface-attached. They then sit at the depth the real ports do.
- Put a GT-1W wing on each of the PPE's two wing nodes.
- HALO and I-Hab each have an `arm` node where the real station's arms are mounted.

## Building from source

The parts are generated from NASA's `Gateway Core.glb` by headless Blender 3.6 scripts:

1. Install Blender 3.6 LTS and taniwha's [io_object_mu](https://github.com/taniwha/io_object_mu) add-on.
2. Apply `tools/io_object_mu-submesh.patch` to the add-on. Without it, KSP draws multi-material meshes with the wrong textures.
3. Run `scripts/01_import.py` on the GLB to create `src/gateway_source.blend`.
4. Run `scripts/02_extract_textures.py`, `scripts/uvdump.py` and `scripts/textures.py` to make the textures.
5. Run `./build_all.sh` to build the parts and `./package.sh` to make the release zip.

## Credits and licence

- **3D model and textures:** derived from NASA's "Gateway Core" model, published free for use on [NASA 3D Resources](https://nasa3d.arc.nasa.gov/detail/gateway). Courtesy NASA. NASA does not endorse this mod.
- **Inspiration and reference:** Benjee10's HabTech2. No HabTech2 assets are included.
- **Export tooling:** taniwha's io_object_mu.
- **Mod assets:** CC BY-NC-SA 4.0. **Build scripts:** MIT. See `LICENSE`.
