# Script para auditar dependencias

import re
import subprocess
import sys


from typing import Optional


def parse_package_name(line: str) -> Optional[str]:
    """Extract the base package name from a requirements.txt line (stripping extras like [standard])."""
    line = line.strip()
    if not line or line.startswith("#") or line.startswith("-"):
        return None
    # Split on version specifiers: ==, >=, <=, ~=, !=, >, <
    match = re.split(r"[><=!~]=?", line)
    raw_name = match[0].strip() if match and match[0].strip() else None
    if raw_name:
        # Strip extras bracket notation e.g. uvicorn[standard] -> uvicorn
        base_name = re.split(r"\[", raw_name)[0].strip()
        return base_name
    return None


def check_dependencies():
    """Verify that all packages in requirements.txt are installed."""
    missing = []
    installed_info = []

    try:
        with open("requirements.txt", "r", encoding="utf-8") as file:
            for line in file:
                package = parse_package_name(line)
                if not package:
                    continue

                result = subprocess.run(
                    [sys.executable, "-m", "pip", "show", package],
                    capture_output=True,
                    text=True,
                )
                if result.returncode != 0:
                    missing.append(package)
                else:
                    # Extract installed version
                    for info_line in result.stdout.splitlines():
                        if info_line.startswith("Version:"):
                            version = info_line.split(":", 1)[1].strip()
                            installed_info.append(f"  ✅ {package}=={version}")
                            break
    except FileNotFoundError:
        print("❌ No se encontró requirements.txt")
        return []

    return missing, installed_info


def main():
    missing, installed = check_dependencies()

    print("=" * 50)
    print("  Auditoría de Dependencias - Ruta Clara")
    print("=" * 50)

    if installed:
        print("\nPaquetes instalados:")
        for info in installed:
            print(info)

    if missing:
        print(f"\n⚠️  Dependencias faltantes ({len(missing)}):")
        for package in missing:
            print(f"  ❌ {package}")
        print(f"\nInstala con: pip install {' '.join(missing)}")
    else:
        print("\n✅ Todas las dependencias están instaladas.")


if __name__ == "__main__":
    main()
