# CLAUDE.md — GatewayTech + ShabTech: the Bluedog upgrade (hand-off)

This file carries the state of a planned-and-approved piece of work so another Claude session
(terminal, with Blender 3.6 available) can continue it. Read it fully before touching anything.
The same file is committed in both repos: `lsamman/GatewayTech` and `lsamman/ShabTech`.

## How to work (DreamlinersOrchestration)

Fable orchestrates and reviews; Opus, Sonnet and Haiku execute. Install the skill once:
`mkdir -p ~/.claude/skills/DreamlinersOrchestration && curl -fsSL https://raw.githubusercontent.com/lsamman/DreamlinersOrchestration/main/skills/DreamlinersOrchestration/SKILL.md -o ~/.claude/skills/DreamlinersOrchestration/SKILL.md`
then `/model claude-fable-5-2`, `/advisor fable`, and `/DreamlinersOrchestration`.
Rules: do small jobs directly; cheapest capable tier first; short briefs that point at files; executors
never commit; Fable reviews diffs, commits, opens PRs. **Merge only when the owner says so.**

## The goal

Make both mods look and behave more like Bluedog Design Bureau (reference: the `1.14-Development`
branch of `CobaltWolf/Bluedog-Design-Bureau`, 3.4 GB; clone it read-only next to the repos, or use
the hardcoded targets below). Owner's decisions:
- **Textures**: yes, via a scripted post-process (see targets).
- **Models**: material-level edits anywhere; **geometry work only on the owner's machine** with
  Blender 3.6 + io_object_mu, verified in Blender and in KSP.
- **Configs**: every Bluedog convention on the list below **except** replacing real company names
  with fictional ones (keep NASA, Northrop Grumman, ESA, MDA, Maxar in descriptions).

## How the two mods are built (facts, verified)

**GatewayTech** (`lsamman/GatewayTech`): parts generated from NASA's `Gateway Core.glb` by headless
Blender 3.6 scripts. `scripts/textures.py` turns glTF PBR maps into KSP `_diff` (RGB + gloss in alpha)
and `_nrm` (DXT5nm: R=1, G=B=Y, A=X) DDS; `scripts/make_cfgs.py` writes every `Parts/*.cfg` from
`build/mu/*.json`. **`src/`, `build/`, `release/` are gitignored**, so a fresh clone cannot run
`make_cfgs.py` or regenerate textures from source: cfg changes must go into **both** `make_cfgs.py`
(template `:395-417`, `COMMON` `:9-18`, `PARTS` from `:151`) **and** the committed cfgs, and the
texture pass must work DDS→DDS as well as inside `textures.py`. Materials: `KSP/Bumped Specular`
(`scripts/gt_lib.py:146`). No emissive maps exist. 10 parts, 25 DDS (1024² hull maps).

**ShabTech** (`lsamman/ShabTech`): everything modelled and textured procedurally from scratch
(`scripts/build_*.py`, `scripts/tex_*.py`, `scripts/tl.py` helpers, `scripts/greebles.py`,
`scripts/bake_ao.py` — Cycles AO bake, needs Blender). Cfgs are hand-written (14 parts in
`GameData/SHABTech/Parts/`), checked by `scripts/lint.py` (braces, model/texture existence, transform and
animation names, B9 tank types). Hull maps are 2048² DXT5, gloss in alpha, gentle normals. It already
has emissive window/lamp maps, `ModuleColorChanger`, floodlights, an agency, B9PartSwitch, and
Waterfall / VABOrganizer / FreeIva / KAS / CCK patches. `tex_hull.py` needs a DejaVu Bold font: add
`/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf` to the list at `scripts/tl.py:21` on Debian.

**Tooling facts**: `pip install bpy` gives only Blender 5.x (Python 3.13); `bpy==3.6.0` is not on
PyPI any more. Under bpy 5.3, io_object_mu loads with two shims (`shader.create_nodes` no-op;
`import_mu.create_action` stubbed) and imports/exports static meshes, **but drops animations**.
io_object_mu's **pure-Python `mu.py`** reads and writes `gt_HALO.mu` with every mesh, collider and the
`antennaDeploy` clip intact (file size identical; ~123 kB of bytes differ — first task below is to
prove vertex data is numerically equal). That is the route for shader/material edits without Blender.
The repo's `scripts/mudump.py` already reads `.mu` this way. Apply `tools/io_object_mu-submesh.patch`
to any io_object_mu checkout.

## Texture targets (measured on paint regions only: luma > .45, saturation < .12)

| | Bluedog (OWS / MOL) | GatewayTech (HALO / I-Hab) | ShabTech (fib / mmod) |
|---|---|---|---|
| paint p10 / p50 / p90 | .49 / .76 / .78 | .54 / .69 / .79 | .67 / .77 / .80 · .54 / .60 / .78 |
| crease contrast (p5 of luma − 9px box blur) | **−.05** | −.12 / −.09 (too sharp) | −.09 · −.03 |
| warmth R−B | 0.000 (neutral) | 0.00 | +.02 / −.02 |
| normal std (DXT5nm A channel) | **.09–.11** | .165 (too strong) | .04–.08 |
| gloss p50 (alpha, paint) | .28–.35 | .25–.27 | .25–.34 |

Reading: shader, map layout, white point (p90 .78), gloss and neutral hue already match Bluedog.
The visible gap is **Bluedog's broad, soft baked shading (AO gradients, grime, edge wear) versus
GatewayTech's sharp fine-grain relief and ShabTech's near-uniform panels**. Do NOT darken the shadows
(an earlier whole-atlas p10 of .15 was Bluedog's black regions, not its paint). Do NOT warm the whites.

### A. `scripts/bdb_look.py` (both repos, same core; DDS→DDS; also called from the generators)
1. GatewayTech relief: `NORMAL_GAIN` 1.5→1.0, `DETAIL_GAIN` 2.0→1.1, `CAVITY_GAIN` .30→.20 in
   `textures.py`; for committed DDS, scale normal X/Y toward std ≈ .10. ShabTech normals untouched.
2. Broad shading: mid-frequency occlusion (blurred curvature, radius ~12–24 px, plus UV-island-edge
   darkening) multiplied into diffuse at 8–15%. Target crease contrast ≈ −.05.
3. Grime/edge wear: low-frequency noise ±4%, faint curvature edge highlights; masked off decals,
   windows, emissive texels, non-paint materials.
4. Keep white point, neutrality, gloss-in-alpha, the vertical flip, DXT5nm layout, full mip chain.
   Encoder: `convert` (ImageMagick 6), `-flip -define dds:compression=dxt5 -define dds:cluster-fit=true`.
5. Scope: hull maps only. Not ShabTech `iva`, `ivaglass`, `window`, `lamp_emit`, `chute`, `wiremesh`;
   not GatewayTech `gt_white`, `gt_flat`, `gt_plate`.
6. Pilot one map per mod (HALO_main, shab_fib), render the part before/after (bpy 5.3 static import
   is enough for a still), show the owner, then batch. State the recompression loss.
`--check` mode prints the table above per map against the targets.

### B. Emissive windows for GatewayTech
`scripts/emit.py` → `<mat>_emit.dds` (window texels; black elsewhere; DXT1). Window materials to
`KSP/Emissive/Bumped Specular` with `_Emissive`, applied in `gt_lib.py` (rebuilds) and into the
committed `.mu` via `mu.py`. Bluedog's `ModuleColorChanger` (`shaderProperty = _EmissiveColor`,
`animRate = 0.8`, `defaultActionGroup = Light`, `toggleName = #autoLOC_502011`, on/off
`#autoLOC_502012/3`, curves r,g 0→1, b 0→0.7) into `make_cfgs.py` and HALO, I-Hab, ESPRIT, Airlock.
ShabTech already has this.

### C. Config upgrades (Bluedog conventions; file:line refs are in the Bluedog Skylab/MOL cfgs)
GatewayTech (generator + cfgs): per-part structural values (crewed modules `crashTolerance 6`,
`breakingForce/Torque 2500`, `maxTemp 1000`, `skinMaxTemp 2000`, replacing the shared 8/250/1200/1400);
radiators `emissiveConstant .90, heatConductivity .001, thermalMassModifier 5, radiatorHeadroom .75`;
ROSA `thermalMassModifier 2, emissiveConstant .95, heatConductivity .04`; habs `emissiveConstant .5`;
`TechRequired` advElectrics (radiators, ROSA), specializedConstruction (modules); radiator wings
cost ~2000–2500; **PPE `mass = 0.275` looks 10× light — recompute from the README's 0.25× real dry
rule (real PPE ≈ 5 t → ~1.25 t)** and either add ModuleRCSFX or drop its 12 MonoPropellant; tags with
stock stems (`radiat therm cool temperat`, `hab crew pressur station`); crewReport experiment +
science-container options (`collectActionName`, `allowRepeatedSubjects`, `canTransferInVessel`) on
crewed parts; 200 EC in I-Hab/ESPRIT/Airlock; 1/1/1 reaction wheel on HALO; `isBreakable = true` +
`windResistance = 1` on ROSA and radiators; `#autoLOC_6002401/2/3` for extend/retract/toggle;
`Agencies/Agency.cfg` for "GatewayTech Consortium"; new `Compatibility/` folder, one `:NEEDS[]` file
each: ConnectedLivingSpace (passable crewed modules, `impassablenodes = arm, radA, radB`),
CommunityTechTree (`:FOR[GatewayTech]`), SystemHeat (radiators → `ModuleSystemHeatRadiator`),
USI-LS, TAC-LS, Snacks, Waterfall (PPE ion plume on `plumeLarge`/`plumeSmall`), KSPRescuePodFix,
VABOrganizer. Update README "Requirements/Optional".
ShabTech (cfgs + `Patches/`): `breakingForce/Torque` on HGA, RadiatorWing, both UltraFlex;
`skinMaxTemp` on Adapter, HGA, Leg, RadiatorWing, RoverWheel, both UltraFlex; radiator thermal fields
on ReactorRover; `entryCost` to 2–3× cost on the 12 parts outside that band; `isBreakable = true` on
UltraFlex arrays and RadiatorWing; `#autoLOC` for ReactorRover radiator and PCM shutter actions;
`uiGroupName`/`uiGroupDisplayName` on the PCM's two B9 switchers; new `SHAB_CLS.cfg`, `SHAB_CTT.cfg`,
`SHAB_SystemHeat.cfg`, USI-LS/TAC-LS/Snacks patches scaled to the PCM's 4 crew; font path in `tl.py`.
Bluedog patterns judged NOT worth copying: its plugin modules (`ModuleBdbJettison`), `techtag`/
`real_title` strip-fields, placeholder IVAs, KIS inventories, hand-written DRAG_CUBEs, unguarded B9.

### D. Model work (owner's machine only)
1. Rebuild `.mu` with `build_all.sh` after the emissive material change; confirm in KSP.
2. Geometry passes in the Blender build scripts, verified in Blender 3.6 and KSP: Gateway —
   handrails, MLI seams, trunnions, grapple fixtures, window frames; ShabTech — greeble density,
   panel bevels (`greebles.py`, `bake_ao.py` for real AO instead of the scripted approximation).
Never edit animated parts (arms, wings, radiators, antennas, chutes, HIAD, legs) with headless bpy 5.x.

## Verification before any PR
- `bdb_look.py --check` within targets; before/after renders of the pilot parts shown to the owner.
- `mu.py` round trip: all vertex/normal/uv/tangent arrays and clips of `gt_HALO.mu` numerically equal.
- Every cfg parses (braces/`=`); every `:NEEDS[]` names a real mod folder; every referenced texture,
  model, transform, animation exists (extend ShabTech `lint.py` to GatewayTech).
- GatewayTech: the generator's output for one part matches the hand-edited cfg.
- In-game check in KSP on the owner's machine.

## State (updated 2026-11-12, Fable 5.1 session, owner's machine)

Corrections to the facts above, found on the owner's machine: Blender 3.6 + io_object_mu and the gitignored
`build/`, `src/` are present, so material changes go through `gt_lib.py` + `build_all.sh` (the `mu.py`
byte-patching route is not needed). ShabTech's cfg source of truth is `cfg/` + `patches/`; `build_all.sh`
deletes and regenerates `GameData/SHABTech` (`SKIP_MODELS=1 SKIP_TEX=1 ./build_all.sh` for cfg-only
changes; it also deletes the tracked `Parts/@thumbs/`, restore with `git checkout`). ImageMagick is v7
(`magick`). Bluedog is installed in the Sol KSP GameData (`Bluedog_DB`), so it can be measured locally.

**Done, reviewed by Fable, merged into `claude/bdb-upgrade` in both repos (local only, NOT pushed):**
- C (both repos): all config items above. PPE bus = 0.95 t (0.25 × 5 t − 2 × 0.15 t ROSA), MonoPropellant
  dropped (no RCS transforms). PCM shutters keep plain `Open/Close/Toggle Shutters` (`#autoLOC_600240x`
  contain `<<1>>` and only work on ModuleDeployableRadiator). GatewayTech Agency logo is a placeholder
  (`gt_white_diff`); a real flag is still to be made. `scripts/lint.py` now exists in GatewayTech too.
- B: `scripts/emit.py` + `gt_lib.material()` switch to `KSP/Emissive/Bumped Specular` when
  `build/tex/<mat>_emit.dds` exists; `build_all.sh` runs emit.py first. Only ESPRIT (ERMXL_main/aux) has
  window glass in the source atlases; HALO_main's map lights its camera/lamp lenses; I-Hab and Airlock have
  no glass texels, so they keep the plain shader and got NO ModuleColorChanger (HALO and ESPRIT have it).
  Rebuilt `gt_HALO.mu`, `gt_ESPRIT.mu`; clips verified intact.

**A (textures): DONE, reviewed by Fable and merged into `claude/bdb-upgrade` in both repos on 2026-11-12**
(merge commits "Merge wt/gt-tex" / "Merge wt/sh-tex"; local only, NOT pushed). `scripts/bdb_look.py` is the same file in
both repos. 20 of 22 maps pass `--check` (all 11 GT materials at crease ≈ −.05, normal std .100; p90/warmth/gloss
unchanged everywhere). `shab_isru` (−.006) and `shab_rover` (−.022) are exempt from the crease target: flat paint
with nothing to soften, they got the maximum contact shading and stay as processed. ShabTech is measured on
UV-covered paint only (`bdb_look.py --dump-uv` writes `build/uvdump.json`; `--measure-cover`); maps softer than −.04
get island-edge darkening up to 15%. Generators are wired and proven: `textures.py` (gains 1.0/1.1/0.20,
`GLOSS_CAVITY` .30, calls `look()` + `scale_normal()`), `tl.py` (`HULL` tuple, `bdb_pass()` in `Canvas.save()`).
The merged DDS were copied into each main checkout's `build/tex`, so `build_all.sh` reuses them. Lint: 0 errors in
both trees. Both mods deployed to the Sol install with `./deploy.sh` for the owner's in-game check. The worktrees
`~/Projects/wt/gt-tex` and `sh-tex` still hold the originals (`build/pilot/orig/`), tables (`batch_check.txt`) and
renders; `git worktree remove` them once the owner has judged the textures in game.

**Next, in order:** owner judges the batched textures in game → push `claude/bdb-upgrade` in both repos, one PR
per repo → merge to main only on the owner's say-so. D (geometry) not started.
