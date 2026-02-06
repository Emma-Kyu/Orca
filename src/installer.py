import argparse
import os
import subprocess
import sys
from pathlib import Path

def run(cmd, cwd=None):
	print(f"> {' '.join(cmd)}")

	# robocopy uses non-zero exit codes to signal "success with changes".
	# 0-7 are success states; 8+ indicates failure.
	if len(cmd) > 0 and str(cmd[0]).lower() == "robocopy":
		result = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
		if result.returncode >= 8:
			raise subprocess.CalledProcessError(result.returncode, cmd)
		return

	subprocess.check_call(cmd, cwd=str(cwd) if cwd else None)

def write_env(project_root: Path, orca_root: Path):
	vendor_bin = (orca_root / "vendor" / "bin").resolve()
	logs_dir = (project_root / "logs" / "subprocesses").resolve()

	env_text = "\n".join([
		"# Hosting addresses",
		"HOST_ADDRESS=127.0.0.1",
		"",
		"# Connectivity",
		"WEBSOCKET_PORT=49170",
		"",
		"# Internal connectivity",
		"LLM_PORT=15324",
		"STT_PORT=15325",
		"",
		"# Log directories",
		f"SUBPROCESS_LOG_DIR={logs_dir}",
	])

	(project_root / ".env").write_text(env_text, encoding="utf-8")
	logs_dir.mkdir(parents=True, exist_ok=True)

def ensure_vendor_dirs(orca_root: Path):
	(orca_root / "vendor" / "bin").mkdir(parents=True, exist_ok=True)

def main():
	parser = argparse.ArgumentParser()
	parser.add_argument("--project-root", default=".", help="Consuming project root where .env will be written")
	args = parser.parse_args()

	project_root = Path(args.project_root).resolve()

	orca_root = orca_root = Path(__file__).resolve().parents[1]  # src/orca_installer/cli.py -> Orca/
	ensure_vendor_dirs(orca_root)
	write_env(project_root, orca_root)

	vendor_dir = orca_root / "vendor"
	bin_dir = vendor_dir / "bin"

	# Clone + build llama.cpp
	llama_dir = vendor_dir / "llama.cpp"
	if not llama_dir.exists():
		run(["git", "clone", "https://github.com/ggml-org/llama.cpp.git"], cwd=vendor_dir)

	run([
		"cmake", "-B", "build",
		"-DGGML_CUDA=ON",
		'-DCMAKE_CUDA_ARCHITECTURES=86',
		"-DGGML_CUDA_F16=ON",
		"-DGGML_CUDA_FORCE_MMQ=ON",
		"-DGGML_CUDA_PEER_MAX_BATCH_SIZE=1",
		"-DLLAMA_CURL=OFF",
		"-DGGML_NATIVE=ON",
	], cwd=llama_dir)

	run([
		"cmake", "--build", "build", "--config", "Release",
		"--target", "llama-bench",
		"--target", "llama-perplexity",
		"--target", "llama-quantize",
		"--target", "llama-server",
		"--parallel",
	], cwd=llama_dir)

	# Copy built binaries into vendor/bin/llama.cpp
	llama_out = bin_dir / "llama.cpp"
	llama_out.mkdir(parents=True, exist_ok=True)
	run(["robocopy", r".\build\bin\Release", str(llama_out), "/E"], cwd=llama_dir)

	# Clone + build whisper.cpp
	whisper_dir = vendor_dir / "whisper.cpp"
	if not whisper_dir.exists():
		run(["git", "clone", "https://github.com/ggml-org/whisper.cpp.git"], cwd=vendor_dir)

	# Replace server example with your custom server code
	server_dir = whisper_dir / "examples" / "server"
	if server_dir.exists():
		run(["cmd", "/c", "rmdir", "/s", "/q", "server"], cwd=whisper_dir / "examples")
	run(["git", "clone", "https://github.com/Emma-Kyu/Whisper-Server-Code.git", "server"], cwd=whisper_dir / "examples")

	run([
		"cmake", "-B", "build",
		"-DGGML_CUDA=ON",
		'-DCMAKE_CUDA_ARCHITECTURES=86',
		"-DGGML_CUDA_F16=ON",
		"-DGGML_CUDA_FORCE_MMQ=ON",
		"-DGGML_NATIVE=ON",
	], cwd=whisper_dir)

	run(["cmake", "--build", "build", "-j", "--config", "Release", "--parallel"], cwd=whisper_dir)

	whisper_out = bin_dir / "whisper.cpp"
	whisper_out.mkdir(parents=True, exist_ok=True)
	run(["robocopy", r".\build\bin\Release", str(whisper_out), "/E"], cwd=whisper_dir)

	print("\nDone. Wrote .env to:", project_root / ".env")
	print("Vendor binaries at:", bin_dir)

if __name__ == "__main__":
	main()
