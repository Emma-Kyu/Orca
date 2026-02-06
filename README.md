# 🐋 Orca
Orca is a lightweight **AI orchestrator**.

It is primarily built to run **Emma**, but it is not hard-wired to her. Orca’s job is to coordinate models, tools, and subprocesses based on a YAML configuration, rather than containing any personality or business logic itself.

---
# Setup
> These defaults are tuned for CUDA with a single RTX 3090.
> Other GPUs will work, but performance and build flags may need adjustment.
## 1) Install the module
From your project that will *use* Orca:
```bash
pip install -e ../Orca
```
Editable install is recommended while developing Orca.

If you are not developing Orca itself, you can also install normally:
```bash
pip install Orca
```
---
## 2) Set up your project
From the **consumer project root**, run:
```bash
orca-install --project-root .
```
This will:
* compile **llama.cpp**
* compile **whisper.cpp**
* create Orca’s internal `vendor/` directory
* generate a `.env` file in your project root with sane defaults
This step can take a while and **requires internet access** the first time.
---
# ▶️ Running Orca with a config
Orca is driven entirely by **YAML configs**.
The executable does not hardcode behavior.
## Example config template
```yaml
name: HomeGPT
chat:
  backend: "llama.cpp"
  model_path: "./data/models/assistant-model.gguf"
  context_length: 16384
  silence_token: "<silence>"
  function_token: "`"
  thinking_token: "<thinking>"
  system_prompt: |
    Date: <time>
    You are a helpful AI assistant.
```
You can extend this file with additional backends, tools, or behaviors as your system grows.

---
## Running a config
From your project root:
```bash
Orca config.yaml
```
Orca will:
* read your YAML
* load the specified backend
* start required subprocesses
* begin orchestrating interactions according to your config
---
# System prompt replacements
Orca supports **template variables** inside `system_prompt`.
These look like:
```
<name>
```
Clients can define their own replacements, and Orca provides several built-ins.
## Built-in replacements
* `<date>`
  replaced with the current date in `YYYY-MM-DD` format
* `<time>`
  replaced with the current time in `HH:MM AM/PM` format
* `<functions>`
  replaced with any functions registered by connected clients
This allows your prompt to stay static while Orca injects dynamic context at runtime.