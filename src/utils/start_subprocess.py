import subprocess
import os
import threading
import socket
from datetime import datetime
from pathlib import Path

def start_subprocess(cmd, logs_dir: str = "."):
	_program = os.path.basename(cmd[0] if isinstance(cmd, (list, tuple)) and cmd else str(cmd))
	# Ensure it exists
	Path(logs_dir).mkdir(parents = True, exist_ok = True)

	start_dt = datetime.now()
	log_path = os.path.join(
		logs_dir,
		f"{start_dt.strftime('%Y-%m-%d-%H-%M')}-{_program}.log"
	)

	p = subprocess.Popen(
		cmd,
		stdout = subprocess.PIPE,
		stderr = subprocess.PIPE,
		text = True,
		errors = "replace",
		bufsize = 1
	)

	# Open immediately so the log exists from process start
	log_file = open(log_path, "w", encoding = "utf-8", buffering = 1)

	def _write_header():
		log_file.write("-" * 80 + "\n")
		log_file.write("# Command\n")
		log_file.write(f"{cmd}\n")
		log_file.write("# Start time\n")
		log_file.write(f"{start_dt.isoformat(sep=' ', timespec='seconds')}\n")
		log_file.write("-" * 80 + "\n")

	def _pump_stream(stream, label: str):
		# Stream line-by-line so logs update live
		if stream is None:
			return
		try:
			for line in stream:
				log_file.write(f"[{label}] {line}")
		except Exception as e:
			log_file.write(f"[LOGGER] Error reading {label}: {e}\n")

	def _termination_signal(code: int) -> str:
		if code is None:
			return "UNKNOWN"
		if code >= 0:
			return "NONE"
		return f"SIG{-code}"

	def _wait_and_log():
		# If we have pipes, capture output; otherwise just wait
		stdout_t = threading.Thread(
			target = _pump_stream,
			args = (p.stdout, "STDOUT"),
			daemon = True
		)
		stderr_t = threading.Thread(
			target = _pump_stream,
			args = (p.stderr, "STDERR"),
			daemon = True
		)

		stdout_t.start()
		stderr_t.start()

		p.wait()

		# Let pump threads finish draining
		stdout_t.join(timeout = 2.0)
		stderr_t.join(timeout = 2.0)

		end_dt = datetime.now()
		code = p.returncode
		runtime = (end_dt - start_dt).total_seconds()
		hostname = socket.gethostname()
		signal = _termination_signal(code)

		log_file.write("\n" + "-" * 80 + "\n")
		log_file.write("# End time\n")
		log_file.write(f"{end_dt.isoformat(sep=' ', timespec='seconds')}\n")
		log_file.write("# Runtime (seconds)\n")
		log_file.write(f"{runtime:.3f}\n")
		log_file.write("# Exit code\n")
		log_file.write(f"{code}\n")
		log_file.write("# Termination signal\n")
		log_file.write(f"{signal}\n")
		log_file.write("# Hostname\n")
		log_file.write(f"{hostname}\n")
		log_file.write("-" * 80 + "\n")

		log_file.close()

		print(f"{_program} exited with code {code}")

	threading.Thread(target = _wait_and_log, daemon = True).start()
	return p