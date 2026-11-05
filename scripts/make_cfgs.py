"""Write GatewayTech part configs from build/mu/*.json and assemble GameData/GatewayTech.
usage: python3 -I scripts/make_cfgs.py <build/mu> <build/tex> <GameData/GatewayTech>"""
import json, os, shutil, sys

mu_dir, tex_dir, out = sys.argv[1:4]
parts_dir = os.path.join(out, 'Parts')
os.makedirs(parts_dir, exist_ok=True)

COMMON = """\
	module = Part
	author = lsamman
	manufacturer = GatewayTech Consortium
	rescaleFactor = 1
	dragModelType = default
	maximum_drag = 0.2
	minimum_drag = 0.2
	angularDrag = 2
	crashTolerance = 8
	breakingForce = 250
	breakingTorque = 250
	maxTemp = 1200
	skinMaxTemp = 1400
"""

ANTENNA = """\
	MODULE
	{{
		name = ModuleDeployableAntenna
		showStatus = false
		isTracking = false
		pivotName = {pivot}
		windResistance = 1
		animationName = antennaDeploy
		extendActionName = Extend Antennas
		retractActionName = Retract Antennas
		extendpanelsActionName = Toggle Antennas
	}}
	MODULE
	{{
		name = ModuleDataTransmitter
		antennaType = {kind}
		packetInterval = 0.25
		packetSize = 2
		packetResourceCost = 20.0
		requiredResource = ElectricCharge
		DeployFxModules = 0
		antennaPower = {power}
		antennaCombinable = True
	}}
"""

RADIATOR = """\
	MODULE
	{{
		name = ModuleDeployableRadiator
		animationName = radiatorDeploy
		showStatus = false
		retractable = true
		isTracking = false
		isBreakable = false
		pivotName = {pivot}
		raycastTransformName = {pivot}
		windResistance = 2.5
		extendActionName = Extend Radiators
		retractActionName = Retract Radiators
		extendpanelsActionName = Toggle Radiators
	}}
	MODULE
	{{
		name = ModuleActiveRadiator
		maxEnergyTransfer = {energy}
		overcoolFactor = 0.25
		isCoreRadiator = true
		RESOURCE
		{{
			name = ElectricCharge
			rate = {ec}
		}}
	}}
"""

SOLAR = """\
	MODULE
	{{
		name = ModuleDeployableSolarPanel
		resourceName = ElectricCharge
		chargeRate = {rate}
		sunTracking = true
		isBreakable = false
		retractable = true
		animationName = wing{tag}_deploy
		pivotName = sunPivot{tag}
		raycastTransformName = sunCatcher{tag}
		extendActionName = Extend Wing {tag}
		retractActionName = Retract Wing {tag}
		extendpanelsActionName = Toggle Wing {tag}
	}}
"""

CARGO = """\
	MODULE
	{{
		name = ModuleCargoPart
		packedVolume = {vol}
	}}
"""

CREW = """\
	CrewCapacity = {crew}
	INTERNAL
	{{
		name = {iva}
	}}
	MODULE
	{{
		name = ModuleInventoryPart
		InventorySlots = {slots}
		packedVolumeLimit = 400
	}}
	MODULE
	{{
		name = ModuleScienceContainer
		reviewActionName = Review Stored Data
		storeActionName = Store Experiments
		evaOnlyStorage = True
		storageRange = 2
	}}
"""


def res(name, amount, maxa=None):
    return f"\tRESOURCE\n\t{{\n\t\tname = {name}\n\t\tamount = {amount}\n\t\tmaxAmount = {maxa or amount}\n\t}}\n"


# Mass basis: HabTech2 scales its ISS modules to ~0.25x real mass (Destiny 14.5 t -> 4,
# Unity 11.6 -> 2.5, Harmony 14.3 -> 3, Columbus 10.3 -> 3, Quest 6.1 -> 1.4; mean 0.245).
# GatewayTech uses MASS_SCALE = 0.25 on real masses; `mass` below is DRY, resources add on top.
#   XenonGas 0.1 kg/unit, MonoPropellant (hydrazine) 4 kg/unit.
#   PPE      5,000 kg launch (NASA): ~2,300 dry + 2,500 Xe + ~200 N2H4  -> 0.575 t dry, of which
#            two ROSA wings ~600 kg each (estimate)                       -> bus 0.275 t + 2 x gt_ROSA 0.15 t
#   HALO     no published mass; ~8,000 kg estimated (enlarged Cygnus PCM)  -> 2.0 t
#   I-Hab    10,000 kg (ESA)                                                -> 2.5 t, of which
#            two accordion radiator wings ~400 kg each (estimate)        -> 2.3 t + 2 x gt_IHabRadiator 0.1 t
#   ESPRIT   10,000 kg (ESA): ~2,000 Xe + ~800 N2H4 refuelling load      -> 1.8 t + 5000 Xe + 50 MP
#   Airlock  10,000 kg (MBRSC / Thales Alenia)                             -> 2.5 t, of which
#            two radiator wings ~200 kg each (estimate)                   -> 2.4 t + 2 x gt_AirlockRadiator 0.05 t
#   Canadarm3 large arm 715 kg (CSA)                                        -> 0.18 t
#   Dexterous arm ~360 kg (CSA system estimate 1,076 kg minus large arm)   -> 0.09 t
MASS_SCALE = 0.25

PARTS = {
    'gt_PPE': dict(
        title='GT-1 "Helios" Power & Propulsion Element',
        description='Lunar Gateway Power and Propulsion Element (PPE), built by Maxar for NASA. The heart of the outpost: a high-power solar-electric bus whose Hall-effect thrusters keep the station in its lunar orbit. Mount two GT-1W roll-out solar wings on its wing mounts for power.',
        tech='advElectrics', cost=36000, entry=30000, mass=0.275, category='Electrical',
        profiles='size2', attach='1,0,1,1,0', tags='gateway lunar station ppe power propulsion solar xenon ion roll out rosa',
        extra=ANTENNA.format(pivot='antennaL', kind='DIRECT', power='100000000000') + """\
	MODULE
	{
		name = ModuleCommand
		minimumCrew = 0
		RESOURCE
		{
			name = ElectricCharge
			rate = 0.05
		}
		hasHibernation = True
	}
	MODULE
	{
		name = ModuleSAS
		SASServiceLevel = 3
	}
	MODULE
	{
		name = ModuleReactionWheel
		PitchTorque = 10
		YawTorque = 10
		RollTorque = 10
		RESOURCE
		{
			name = ElectricCharge
			rate = 0.3
		}
	}
	MODULE
	{
		name = ModuleEnginesFX
		thrustVectorTransformName = thrustTransform
		exhaustDamage = False
		ignitionThreshold = 0.1
		minThrust = 0
		maxThrust = 3
		heatProduction = 0
		powerEffectName = IonPlume
		EngineType = Electric
		PROPELLANT
		{
			name = XenonGas
			ratio = 0.1
			DrawGauge = True
		}
		PROPELLANT
		{
			name = ElectricCharge
			ratio = 1.8
			DrawGauge = True
		}
		atmosphereCurve
		{
			key = 0 2800
			key = 1 100
			key = 1.2 0.001
		}
	}
""" + res('ElectricCharge', 1000) + res('XenonGas', 6250) + res('MonoPropellant', 12)),
    'gt_ROSA': dict(
        title='GT-1W "Helios" Roll-Out Solar Wing',
        description='Lunar Gateway Power and Propulsion Element roll-out solar array (ROSA) wing, built by Redwire for the PPE. A flexible blanket array that rolls out between two booms and tracks the sun. Fits the PPE wing mounts, or any surface.',
        tech='advElectrics', cost=9000, entry=12000, mass=0.15, category='Electrical',
        profiles='srf', attach='1,1,0,0,0', tags='gateway lunar station ppe solar array roll out rosa wing panel',
        node_attach='0.0, 0.0, 0.0, 0.0, -1.0, 0.0',
        extra="""\
	MODULE
	{
		name = ModuleDeployableSolarPanel
		resourceName = ElectricCharge
		chargeRate = 30
		sunTracking = true
		isBreakable = false
		retractable = true
		animationName = deploy
		pivotName = sunPivot
		raycastTransformName = sunCatcher
		extendActionName = Extend Solar Wing
		retractActionName = Retract Solar Wing
		extendpanelsActionName = Toggle Solar Wing
	}
	MODULE
	{
		name = ModuleCargoPart
		packedVolume = 800
	}
"""),
    'gt_HALO': dict(
        title='GT-2 "Halo" Habitation & Logistics Outpost',
        description='Lunar Gateway Habitation and Logistics Outpost (HALO), built by Northrop Grumman for NASA. The outpost\'s first living quarters and its command-and-control hub; it runs the station even when nobody is home and carries the main batteries. Three recessed docking seats take NDS docking ports; twin dish antennas fold out for the link home.',
        tech='spaceExploration', cost=9800, entry=14000, mass=2.0, category='Utility',
        profiles='size1p5, size1', attach='1,0,1,1,0', tags='gateway lunar station halo habitation node logistics',
        extra=CREW.format(crew=2, iva='ht2_genericShortIVA', slots=4)
        + ANTENNA.format(pivot='antennaL', kind='RELAY', power='50000000000') + """\
	MODULE
	{
		name = ModuleCommand
		minimumCrew = 0
		hasHibernation = True
		RESOURCE
		{
			name = ElectricCharge
			rate = 0.02
		}
	}
""" + res('ElectricCharge', 2000)),
    'gt_IHab': dict(
        title='GT-3 "Hestia" International Habitation Module',
        description='Lunar Gateway International Habitation Module (I-Hab), built by ESA and Thales Alenia Space with JAXA. The outpost\'s main living space, with four recessed docking seats and two mounts for GT-3R accordion radiator wings to dump the heat of a busy crew.',
        tech='spaceExploration', cost=10500, entry=16000, mass=2.3, category='Utility',
        profiles='size2, size1', attach='1,0,1,1,0', tags='gateway lunar station ihab habitation module radiator',
        extra=CREW.format(crew=3, iva='ht2_destinyIVA', slots=6)),
    'gt_IHabRadiator': dict(
        title='GT-3R "Hestia" Accordion Radiator Wing',
        description='One of the I-Hab\'s two accordion radiator wings: four panels that fold out zig-zag to dump the heat of a busy crew. Fits the I-Hab radiator mounts, or any surface.',
        tech='spaceExploration', cost=1000, entry=6000, mass=0.1, category='Thermal',
        profiles='srf', attach='1,1,0,0,0', tags='gateway lunar station ihab radiator accordion wing thermal heat',
        node_attach='0.0, 0.0, 0.0, 0.0, -1.0, 0.0',
        extra=RADIATOR.format(pivot='radiator_p0', energy=30000, ec=0.3) + CARGO.format(vol=300)),
    'gt_ESPRIT': dict(
        title='GT-4 "Iris" Refuelling Module',
        description='Lunar Gateway ESPRIT Refuelling Module (European System Providing Refuelling, Infrastructure and Telecommunications), built by ESA and Thales Alenia Space. A refuelling tank farm topped with a ring of viewing windows; carries xenon and hydrazine (monopropellant) to top up the Power and Propulsion Element.',
        tech='advFuelSystems', cost=28000, entry=11000, mass=1.8, category='FuelTank',
        profiles='size1p5, size1', attach='1,0,1,1,0', tags='gateway lunar station esprit refuel tank xenon window',
        extra=CREW.format(crew=1, iva='ht2_genericShortIVA', slots=2)
        + res('XenonGas', 5000) + res('MonoPropellant', 50)),
    'gt_Airlock': dict(
        title='GT-5 "Portal" Crew & Science Airlock',
        description='Lunar Gateway Crew and Science Airlock, the UAE\'s Emirates Airlock built by MBRSC and Thales Alenia Space. An EVA airlock for crew and small science payloads, with two mounts for GT-5R folding radiator wings.',
        tech='spaceExploration', cost=7200, entry=12000, mass=2.4, category='Utility',
        profiles='size1p5, size1', attach='1,0,1,1,0', tags='gateway lunar station airlock eva radiator',
        extra=CREW.format(crew=2, iva='ht2_questIVA', slots=4)),
    'gt_AirlockRadiator': dict(
        title='GT-5R "Portal" Folding Radiator Wing',
        description='One of the Crew and Science Airlock\'s two folding radiator wings. Fits the Airlock radiator mounts, or any surface.',
        tech='spaceExploration', cost=500, entry=4000, mass=0.05, category='Thermal',
        profiles='srf', attach='1,1,0,0,0', tags='gateway lunar station airlock radiator wing thermal heat',
        node_attach='0.0, 0.0, 0.0, 0.0, -1.0, 0.0',
        extra=RADIATOR.format(pivot='radiator_p0', energy=17500, ec=0.2) + CARGO.format(vol=150)),
    'gt_Canadarm3': dict(
        title='GT-R1 "Long Reach" Station Arm',
        description='Lunar Gateway Canadarm3 large arm, built by MDA for the Canadian Space Agency. An 8.5 m two-boom station arm; its joints are ornamental, and it unfolds from its stowed position on command.',
        tech='advConstruction', cost=6000, entry=9000, mass=0.18, category='Utility',
        profiles='srf', attach='1,1,0,0,1', tags='gateway lunar station arm canadarm robotic',
        node_attach='0.0, 0.0, 0.0, 0.0, -1.0, 0.0',
        extra="""\
	MODULE
	{
		name = ModuleAnimateGeneric
		animationName = armDeploy
		actionGUIName = Toggle Arm
		startEventGUIName = Unfold Arm
		endEventGUIName = Stow Arm
		allowAnimationWhileShielded = False
	}
	MODULE
	{
		name = ModuleCargoPart
		packedVolume = 600
	}
"""),
    'gt_DexArm': dict(
        title='GT-R2 "Fingertip" Dexterous Arm',
        description='Lunar Gateway Canadarm3 small dexterous arm, built by MDA for the Canadian Space Agency. A nimble manipulator for fiddly jobs around the station; it unfolds on command.',
        tech='advConstruction', cost=3200, entry=6000, mass=0.09, category='Utility',
        profiles='srf', attach='1,1,0,0,1', tags='gateway lunar station arm dexterous robotic',
        node_attach='0.0, 0.0, 0.0, 0.0, -1.0, 0.0',
        extra="""\
	MODULE
	{
		name = ModuleAnimateGeneric
		animationName = armDeploy
		actionGUIName = Toggle Arm
		startEventGUIName = Extend Arm
		endEventGUIName = Stow Arm
		allowAnimationWhileShielded = False
	}
	MODULE
	{
		name = ModuleCargoPart
		packedVolume = 200
	}
"""),
}

ION_EFFECTS = """\
	EFFECTS
	{
		IonPlume
		{
			AUDIO
			{
				channel = Ship
				clip = sound_IonEngine
				volume = 0.0 0.0
				volume = 0.05 0.20
				volume = 1.0 0.25
				pitch = 0.0 0.2
				pitch = 1.0 0.8
				loop = true
			}
			MODEL_MULTI_PARTICLE
			{
				name = plumeLarge
				modelName = Squad/FX/IonPlume
				transformName = plumeLarge
				emission = 0.0 0.0
				emission = 0.25 0.5
				emission = 1.0 1.0
				localPosition = 0, 0, 0
				localScale = 0.6, 0.6, 0.6
			}
			MODEL_MULTI_PARTICLE
			{
				name = plumeSmall
				modelName = Squad/FX/IonPlume
				transformName = plumeSmall
				emission = 0.0 0.0
				emission = 0.25 0.5
				emission = 1.0 1.0
				localPosition = 0, 0, 0
				localScale = 0.4, 0.4, 0.4
			}
		}
	}
"""

for name, p in PARTS.items():
    meta = json.load(open(os.path.join(mu_dir, f'{name}.json')))
    nodes = []
    for n, (pos, d, size) in meta['nodes'].items():
        # Blender part space (x, y, z) -> Unity (x, z, y)
        nodes.append(f"\tnode_stack_{n} = {pos[0]:.4f}, {pos[2]:.4f}, {pos[1]:.4f}, "
                     f"{d[0]:.4f}, {d[2]:.4f}, {d[1]:.4f}, {size}")
    if 'node_attach' in p:
        nodes.append(f"\tnode_attach = {p['node_attach']}")
    vessel = '' if p['profiles'] == 'srf' else '\tvesselType = Station\n'
    cfg = f"""PART
{{
	name = {name}
{COMMON}	TechRequired = {p['tech']}
	entryCost = {p['entry']}
	cost = {p['cost']}
	category = {p['category']}
	subcategory = 0
	title = {p['title']}
	description = {p['description']}
	attachRules = {p['attach']}
	mass = {p['mass']}
	bulkheadProfiles = {p['profiles']}
	tags = {p['tags']}
{vessel}
	MODEL
	{{
		model = GatewayTech/Parts/{name}
	}}

{chr(10).join(nodes)}

{p['extra']}{ION_EFFECTS if name == 'gt_PPE' else ''}}}
"""
    open(os.path.join(parts_dir, f'{name}.cfg'), 'w').write(cfg)
    shutil.copy2(os.path.join(mu_dir, f'{name}.mu'), parts_dir)
    print('wrote', name, len(meta['nodes']), 'nodes')

for f in os.listdir(tex_dir):
    if f.endswith('.dds'):
        shutil.copy2(os.path.join(tex_dir, f), parts_dir)
