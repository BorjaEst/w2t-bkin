"""Example: Create NWBFile from session.toml

This example demonstrates how to use the session module to load
session metadata and create an NWBFile object.
"""

from pathlib import Path

from pynwb import NWBHDF5IO

from w2t_bkin.session import create_nwb_file, get_nwb_metadata_summary


def main():
    """Create and save NWBFile from session.toml"""

    # Path to session configuration
    session_path = Path("data/raw/Session-000001/session.toml")

    print("Creating NWBFile from session.toml...")
    print("-" * 60)

    # Create NWBFile from session.toml
    nwbfile = create_nwb_file(session_path)

    # Print summary
    print(f"\nNWBFile created successfully!")
    print(f"Identifier: {nwbfile.identifier}")
    print(f"Session: {nwbfile.session_id}")
    print(f"Description: {nwbfile.session_description}")
    print(f"Start time: {nwbfile.session_start_time}")
    print(f"Institution: {nwbfile.institution}")
    print(f"Lab: {nwbfile.lab}")

    if nwbfile.subject:
        print(f"\nSubject Information:")
        print(f"  ID: {nwbfile.subject.subject_id}")
        print(f"  Species: {nwbfile.subject.species}")
        print(f"  Sex: {nwbfile.subject.sex}")
        print(f"  Age: {nwbfile.subject.age}")

    if nwbfile.devices:
        print(f"\nDevices ({len(nwbfile.devices)}):")
        for name, device in nwbfile.devices.items():
            print(f"  - {name}")

    # Get metadata summary
    summary = get_nwb_metadata_summary(nwbfile)
    print(f"\nMetadata Summary:")
    print(f"  Keywords: {', '.join(summary['keywords']) if summary['keywords'] else 'None'}")
    print(f"  Experimenters: {', '.join(summary['experimenter']) if summary['experimenter'] else 'None'}")

    # Optionally save to file
    output_dir = Path("output/examples")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "example_session.nwb"

    print(f"\nSaving to: {output_path}")
    with NWBHDF5IO(str(output_path), mode="w") as io:
        io.write(nwbfile)

    print(f"✓ NWB file saved successfully!")

    # Read it back to verify
    print(f"\nVerifying saved file...")
    with NWBHDF5IO(str(output_path), mode="r") as io:
        read_nwbfile = io.read()
        print(f"✓ File readable")
        print(f"  Identifier: {read_nwbfile.identifier}")
        print(f"  Session: {read_nwbfile.session_id}")

    print("\n" + "=" * 60)
    print("Example completed successfully!")


if __name__ == "__main__":
    main()
