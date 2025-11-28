import os
import shutil
import subprocess
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn
from rich.panel import Panel
from rich import box
import importlib.util

console = Console()
pyx_files = []

def auto_annotate_code(py_code: str) -> str:
    lines = py_code.splitlines()
    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        if stripped.startswith("for "):
            parts = stripped.split()
            if len(parts) > 1 and parts[1].isidentifier() and "in range" in stripped:
                indent = len(line) - len(line.lstrip())
                new_lines.append(" " * indent + f"# cdef int {parts[1]} (annotated)")
        elif stripped.startswith("def "):
            indent = len(line) - len(line.lstrip())
            new_lines.insert(len(new_lines), " " * indent + "# @boundscheck(False)")
            new_lines.insert(len(new_lines), " " * indent + "# @wraparound(False)")
            new_lines.insert(len(new_lines), " " * indent + "# @nonecheck(False)")
            new_lines.insert(len(new_lines), " " * indent + "# @cdivision(True)")
        new_lines.append(line)
    if "cimport cython" not in py_code:
        new_lines.insert(0, "# cimport cython")
    return "\n".join(new_lines)

def check_imports(py_file: str):
    missing = []
    with open(py_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("import ") or line.startswith("from "):
                module_name = line.split()[1].split(".")[0]
                if importlib.util.find_spec(module_name) is None:
                    missing.append(module_name)
    return missing

def scan_and_prepare(src_dir: str, out_dir: str):
    total_files = sum(len(f) for _, _, f in os.walk(src_dir) if any(file.endswith(".py") for file in f))
    missing_modules = set()

    with Progress(
        SpinnerColumn(spinner_name="dots"),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task(f"[cyan]Scanning & annotating {src_dir}...📝", total=total_files)
        for root, dirs, files in os.walk(src_dir):
            for f in files:
                if f.endswith(".py"):
                    rel_path = os.path.relpath(root, src_dir)
                    dest_dir = os.path.join(out_dir, rel_path)
                    os.makedirs(dest_dir, exist_ok=True)
                    src_file = os.path.join(root, f)
                    dest_file = os.path.join(dest_dir, f.replace(".py", ".pyx"))
                    code = open(src_file, "r", encoding="utf-8").read()
                    annotated = auto_annotate_code(code)
                    with open(dest_file, "w", encoding="utf-8") as out_f:
                        out_f.write(annotated)
                    pyx_files.append(dest_file)
                    missing_modules.update(check_imports(src_file))
                    progress.update(task, advance=1)

    if missing_modules:
        console.print(f"[bold red]⚠️ Missing modules detected: {', '.join(missing_modules)}[/]")

def build(target: str, output_dir: str):
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    console.print(Panel.fit(f"🚀 Auto-Cythonizer CLI — Compiling {target}", box=box.DOUBLE_EDGE, style="green"))
    scan_and_prepare(target, output_dir)
    console.print(Panel("[yellow]🔧 Compiling .pyx files into .so (with caching)...[/]", style="bold cyan"))

    from Cython.Build import cythonize
    from setuptools import setup

    ext_modules = cythonize(
        pyx_files,
        compiler_directives={
            "boundscheck": False,
            "wraparound": False,
            "nonecheck": False,
            "cdivision": True,
            "language_level": 3
        },
        build_dir="cython_cache",
        cache=True
    )
    setup(script_args=["build_ext", "--inplace"], ext_modules=ext_modules)

    lib_dir = os.path.join("lib", os.path.basename(target))
    if os.path.exists(lib_dir):
        shutil.rmtree(lib_dir)
    os.makedirs(lib_dir, exist_ok=True)
    console.print("[purple]📦 Moving compiled .so files into lib folder...[/]")
    for root, dirs, files in os.walk(output_dir):
        for f in files:
            if f.endswith(".so"):
                rel_path = os.path.relpath(root, output_dir)
                final_dir = os.path.join(lib_dir, rel_path)
                os.makedirs(final_dir, exist_ok=True)
                shutil.move(os.path.join(root, f), os.path.join(final_dir, f))
    console.print("[bold green]✅ Build complete![/]")

def build_wheel_and_install():
    console.print("[blue]📦 Building wheel...[/]")
    subprocess.run(["python", "-m", "build", "--wheel"], check=True)
    wheel_files = [f for f in os.listdir("dist") if f.endswith(".whl")]
    if not wheel_files:
        console.print("[red]❌ No wheel found in dist folder![/]")
        return
    wheel_path = os.path.join("dist", wheel_files[-1])
    console.print(f"[green]🚀 Installing {wheel_path} via pip...[/]")
    subprocess.run(["pip", "install", "--upgrade", wheel_path], check=True)
    console.print("[bold green]✅ Wheel installed successfully![/]")

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Auto-Cythonizer CLI — Compile a Python project folder or a library into Cython extensions"
    )
    parser.add_argument(
        "-t", "--target",
        required=True,
        help="Target folder or Python library to compile"
    )
    parser.add_argument(
        "-o", "--output",
        default="build_lib",
        help="Output directory"
    )
    parser.add_argument(
        "-i", "--install",
        action="store_true",
        help="Build wheel and install"
    )
    args = parser.parse_args()

    build(args.target, args.output)
    if args.install:
        build_wheel_and_install()

if __name__ == "__main__":
    main()
    