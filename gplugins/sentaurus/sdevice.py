import pathlib

from gdsfactory.typings import Floats, Tuple

DEFAULT_OUTPUT_SETTINGS = """Plot{
  *--Density and Currents, etc
  eDensity hDensity
  TotalCurrent/Vector eCurrent/Vector hCurrent/Vector
  eMobility hMobility
  eVelocity hVelocity
  eQuasiFermi hQuasiFermi

  *--Temperature
  eTemperature Temperature * hTemperature

  *--Fields and charges
  ElectricField/Vector Potential SpaceCharge

  *--Doping Profiles
  Doping DonorConcentration AcceptorConcentration

  *--Generation/Recombination
  SRH Band2Band * Auger
  AvalancheGeneration eAvalancheGeneration hAvalancheGeneration

  *--Driving forces
  eGradQuasiFermi/Vector hGradQuasiFermi/Vector
  eEparallel hEparallel eENormal hENormal

  *--Band structure/Composition
  BandGap
  BandGapNarrowing
  Affinity
  ConductionBand ValenceBand

  *--Complex Refractive Index (changed by FCD)
  ComplexRefractiveIndex
}
"""

DEFAULT_PHYSICS_SETTINGS = """Physics{
  Recombination(
    SRH(DopingDep)
    Auger
  )
  Mobility( DopingDep HighFieldSaturation)
  EffectiveIntrinsicDensity( OldSlotboom )
}
"""

DEFAULT_MATH_SETTINGS = """Math{
  Extrapolate
  RelErrControl
  Digits=5
  ErrReff(electron)= 1.0e7
  ErrReff(hole)    = 1.0e7
  Iterations=20
  Notdamped=100
}
"""

DEFAULT_INITIALIZATION = """
    NewCurrentPrefix=\"init\"
    Coupled(Iterations=100){ Poisson }
    Coupled{ Poisson Electron Hole }
"""


def write_sdevice_quasistationary_ramp_voltage_dd(
    struct: str = "struct_out_fps.tdr",
    contacts: Tuple[str] = ("anode", "cathode"),
    ramp_contact_name: str = "anode",
    ramp_final_voltage: float = 1.0,
    ramp_initial_step: float = 0.01,
    ramp_increment: float = 1.3,
    ramp_max_step: float = 0.2,
    ramp_min_step: float = 1e-6,
    ramp_sample_voltages: Floats = (0.0, 0.3, 0.6, 0.8, 1.0),
    filepath: str = "./sdevice_fps.cmd",
    output_settings: str = DEFAULT_OUTPUT_SETTINGS,
    physics_settings: str = DEFAULT_PHYSICS_SETTINGS,
    math_settings: str = DEFAULT_MATH_SETTINGS,
    initialization_commands: str = DEFAULT_INITIALIZATION,
):
    """Writes a Sentaurus Device TLC file for sweeping DC voltage of one terminal of a Sentaurus Structure (from sprocess or structure editor) using the drift-diffusion equations (Hole + Electrons + Poisson).

    You may need to modify the settings or this function itself for better results.

    Arguments:
        struct: Sentaurus Structure object file to run the simulation on.
        contacts: list of all contact names in the struct.
        ramp_contact_name: name of the contact whose voltage to sweep.
        ramp_final_voltage: final target voltage.
        ramp_initial_step: initial ramp step.
        ramp_increment: multiplying factor to increase ramp rate between iterations.
        ramp_max_step: maximum ramping step.
        ramp_min_step: minimum ramping step.
        ramp_sample_voltages: list of voltages between 0V and ramp_final_voltage to report.
        filepath: str = Path to the TLC file to be written.
        file_settings: "File" field settings to add to the TCL file
        output_settings: "Output" field settings to add to the TCL file
        physics_settings: "Physics" field settings to add to the TCL file
        math_settings: str = "Math" field settings to add to the TCL file
        initialization_commands: in the solver, what to execute before the ramp
    """

    # Setup TCL file
    out_file = pathlib.Path(filepath)
    if out_file.exists():
        out_file.unlink()

    # Initialize electrodes
    with open(filepath, "a") as f:
        f.write("Electrode{\n")
        for boundary_name in contacts:
            f.write(f'{{ name="{boundary_name}"      voltage=0 }}\n')
        f.write("}\n")

        # File settings
        f.write("File{\n")
        f.write(f'  Grid    = "{struct}"\n')
        f.write("}\n")

        # Output settings
        f.write(output_settings)

        # Physics settings
        f.write(physics_settings)

        # Math settings
        f.write(math_settings)

        # Solve settings
        f.write("Solve{\n")

        # Initialization
        f.write(initialization_commands)

        ramp_sample_voltages_str = ""
        for i, voltage in enumerate(ramp_sample_voltages):
            if i == 0:
                ramp_sample_voltages_str = f" {voltage}"
            else:
                ramp_sample_voltages_str += f"; {voltage}"

        f.write(
            f"""
    Quasistationary (
        InitialStep={ramp_initial_step} Increment={ramp_increment}
        MaxStep ={ramp_max_step} MinStep = {ramp_min_step}
        Goal{{ Name=\"{ramp_contact_name}\" Voltage={ramp_final_voltage} }}
    ){{ Coupled {{Poisson Electron Hole }}
        Save(FilePrefix=\"sweep\" Time= ({ramp_sample_voltages_str} ) NoOverWrite )
    }}
    """
        )
        f.write("}\n")


def write_sdevice_ssac_ramp_voltage_dd(
    Vfinal: float = 3.0,
    device_name_extra_str="0",
    filepath: str = "./sdevice_fps.cmd",
):
    Vstring = f"{Vfinal:1.3f}".replace(".", "p").replace("-", "m")

    text1 = f"""
Device PN_{Vstring}_{device_name_extra_str} {{

  Electrode {{
    {{ Name="anode" Voltage=0.0 }}
    {{ Name="cathode" Voltage=0.0 }}
    {{ Name="substrate" Voltage=0.0 }}
  }}
"""
    text2 = f"""
  File {{
    Grid = "struct_out_fps.tdr"
    Current = "plot_{Vstring}"
    Plot = "tdrdat_{Vstring}"
  }}
"""
    text3 = f"""
  Physics {{
    Mobility ( DopingDependence HighFieldSaturation Enormal )
    EffectiveIntrinsicDensity(BandGapNarrowing (OldSlotboom))
    Recombination( SRH Auger Avalanche )
  }}
  Plot {{
    eDensity hDensity eMobility hMobility eCurrent hCurrent
    ElectricField eEparallel hEparallel
    eQuasiFermi hQuasiFermi
    Potential Doping SpaceCharge
    DonorConcentration AcceptorConcentration
  }}
}}

Math {{
  Extrapolate
  RelErrControl
  Notdamped=50
  Iterations=20
  NumberOfThreads=4
}}

File {{
  Output = "log_{Vstring}"
  ACExtract = "acplot_{Vstring}"
}}

System {{
  PN_{Vstring}_{device_name_extra_str} trans (cathode=d anode=g substrate=g)
  Vsource_pset vg (g 0) {{dc=0}}
  Vsource_pset vd (d 0) {{dc=0}}
}}

Solve {{
  #-a) zero solution
  Poisson
  Coupled {{ Poisson Electron Hole }}
"""

    text4 = f"""#-b) ramp cathode
  Quasistationary (
  InitialStep=0.01 MaxStep=0.04 MinStep=1.e-5
  Goal {{ Parameter=vd.dc Voltage={Vfinal} }}
  )
"""

    text5 = """
  { ACCoupled (
  StartFrequency=1e3 EndFrequency=1e3
  NumberOfPoints=1 Decade
  Node(d g) Exclude(vd vg)

  )
  { Poisson Electron Hole }
  }
}
"""
    f = open(filepath, "a")
    f.write(text1)
    f.write(text2)
    f.write(text3)
    f.write(text4)
    f.write(text5)
    f.close()


if __name__ == "__main__":
    # write_sdevice_quasistationary_ramp_voltage_dd()
    write_sdevice_ssac_ramp_voltage_dd()
