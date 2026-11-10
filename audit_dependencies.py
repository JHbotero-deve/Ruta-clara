# Script para auditar dependencias

import os
import subprocess

def generate_requirements():
    # Generar requirements.txt
    with open('requirements.txt', 'w') as file:
        subprocess.run(['pip', 'freeze'], stdout=file)

def check_dependencies():
    # Verificar dependencias faltantes
    installed = set()
    missing = []

    with open('requirements.txt', 'r') as file:
        for line in file:
            package, version = line.strip().split('==')
            installed.add(package)

    for package in installed:
        try:
            subprocess.run(['pip', 'show', package], check=True)
        except subprocess.CalledProcessError:
            missing.append(package)

    return missing

def main():
    # Generar requirements.txt
    generate_requirements()

    # Verificar dependencias faltantes
    missing = check_dependencies()

    if missing:
        print("Dependencias faltantes:")
        for package in missing:
            print(f"  - {package}")
    else:
        print("No hay dependencias faltantes.")

if __name__ == "__main__":
    main()