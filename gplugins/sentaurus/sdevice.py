import pathlib

from gdsfactory.typings import Floats, Tuple

DEFAULT_FILE_SETTINGS = """Plot    = \"@tdrdat@\"
  Current = \"@plot@\"
  Output  = \"@log@\"
"""

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
    NewCurrentPrefix=\"n@node@_init\"
    Coupled(Iterations=100){ Poisson }
    Coupled{ Poisson Electron Hole }
"""


def write_sdevice_quasistationary_ramp_voltage_dd(
    struct: str = "./sprocess.tdr",
    contacts: Tuple[str] = ("e1", "e2"),
    ramp_contact_name: str = "e1",
    ramp_final_voltage: float = 1.0,
    ramp_initial_step: float = 0.01,
    ramp_increment: float = 1.3,
    ramp_max_step: float = 0.2,
    ramp_min_step: float = 1e-6,
    ramp_sample_voltages: Floats = (0.0, 0.3, 0.6, 0.8, 1.0),
    filepath: str = "./sdevice_fps.cmd",
    file_settings: str = DEFAULT_FILE_SETTINGS,
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
        f.write("Electrode{{\n")
        for boundary_name in contacts:
            f.write(f'{{ name="{boundary_name}"      voltage=0 }}\n')
        f.write("}}\n")

        # File settings
        f.write(file_settings)
        f.write("File{\n")
        f.write(f'Grid    = "{struct}"\n')
        f.write(DEFAULT_FILE_SETTINGS)
        f.write("}}\n")

        # Output settings
        f.write(output_settings)

        # Physics settings
        f.write(physics_settings)

        # Math settings
        f.write(math_settings)

        # Solve settings
        f.write("Solve{{\n")

        # Initialization
        f.write(initialization_commands)

        ramp_sample_voltages_str = ""
        for voltage in ramp_sample_voltages:
            ramp_sample_voltages_str += f" {voltage} ;"

        f.write(
            f"""
    Quasistationary (
        InitialStep={ramp_initial_step} Increment={ramp_increment}
        MaxStep ={ramp_max_step} MinStep = {ramp_min_step}
        Goal{{ Name={ramp_contact_name} Voltage={ramp_final_voltage} }}
    ){{ Coupled {{Poisson Electron Hole }}
        Save(FilePrefix=\"n@node@\" Time= ({ramp_sample_voltages_str} ) NoOverWrite )
    }}
    """
        )
        f.write("}}\n")


if __name__ == "__main__":
    write_sdevice_quasistationary_ramp_voltage_dd()
