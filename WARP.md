# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project status

- The original Nova project is no longer maintained due to accumulated tech debt. The actively maintained successor is Nova2: https://github.com/00Julian00/Nova2.
- This repository targets Python 3.11 and is designed and tested primarily on Windows (batch launcher, Windows-specific console clearing, CUDA 12.1 instructions).

## How to install and run Nova

### Requirements (from README)

- Python 3.11.x with pip
- Groq API key
- Elevenlabs API key
- mpv
- ffmpeg
- Microsoft C++ Build Tools
- CUDA 12.1 (for GPU-accelerated local models)

Python dependencies are listed in `requirements.txt` and include Groq/Elevenlabs clients, audio I/O, speech/LLM libraries (e.g. `faster-whisper`, `TTS`, `llama-cpp-python`), and support packages.

### Install dependencies

From the repository root:

```bash
# Install CUDA-enabled PyTorch (per README)
pip3 install torch torchaudio --index-url https://download.pytorch.org/whl/cu121

# Install remaining Python dependencies
pip install -r requirements.txt
```

### Configure Nova

Configuration lives under `Nova/Configs` and `LangFiles/`:

- `Nova/Configs/NovaSettings.config` holds user-facing settings (language, hotword, LLM model names, offline mode, stream flag, microphone index, behaviour prompt, and user name).
- `Nova/Configs/KeyList.json` enumerates the logical key names; actual secrets are stored via the OS keyring under the "Nova" service.
- Language files such as `LangFiles/en.json` and `LangFiles/de.json` localize interface strings and must match the core version (`"Version"` field).

Recommended setup flow (as encoded in `README.md` and `Nova/Interface.py`):

1. Run `Start interface.bat` (Windows) from the repo root. This launches the interactive interface in a console titled `Interface`.
2. In the interface, run `keys` to configure API keys. Values are written using `keyring` based on `Nova/Configs/KeyList.json`.
3. Run `micID` to list available microphones and their indexes (via PyAudio), then set `MicrophoneIndex` through `settings`.
4. Optionally adjust other `settings` fields (e.g. behaviour prompt, language code).

### Run the assistant

- **Legacy engine (audio + hotword, Windows-first)**
  - From the repo root: run `Start interface.bat`.
  - In the interface menu, use the `boot` command. This spawns a second terminal window and starts the core engine via `Nova/StartCore.py`.
  - To start the CLI interface without the batch file: `python Nova/Interface.py` from the repo root.
  - To start the core engine directly (without the interface menu): `python Nova/StartCore.py` from the repo root (this calls `Core.Start()`).
- **Experimental nova2 text-only engine (recommended for new development)**
  - From the repo root: `python -m nova2.cli`
  - This uses the new `nova2` package and a separate `nova2.config.json` file at the repo root for configuration.

The main menu commands exposed by the interface (from README and `LangFiles/en.json`):

- `help` – list available interface commands.
- `boot` – start Nova (spawns a separate terminal running the core).
- `keys` – edit API keys via `KeyManager` (values stored securely using keyring).
- `settings` – edit `NovaSettings.config` interactively with validation.
- `exit` – close the interface window (does not stop already running core instances).
- `micID` – list microphones and indexes.
- `clear` – clear the console and reprint the interface header.

### Tests and linting

- This repository does **not** include an explicit test suite or test configuration files (no `tests/` directory, `pytest.ini`, or similar) as of `manifest.json` version 1.6.
- There are no project-specific lint or formatting configs (e.g. no `flake8`, `ruff`, `black`, or `isort` config files). If you introduce tests or linting, prefer standard Python tooling and keep the configuration in version control.

## High-level architecture

Nova is a modular virtual assistant composed of:

- A **console interface** (`Nova/Interface.py`) providing the user-facing main menu.
- A **core engine** (`Nova/Core.py`, `Nova/StartCore.py`) orchestrating audio capture, transcription, LLM inference, speech synthesis, and module/tool invocation.
- **Configuration, language, and key management** in `Nova/Configs`, `LangFiles`, and `Nova/KeyManager.py`.
- A **module system** managed by `Nova/ModuleManager.py` and a `Modules/` directory containing external extensions described by per-module `manifest.json` files.
- A lightweight **API surface** (`NovaAPI.py`) allowing other programs to drive Nova in-process via queues and worker threads.

### Runtime flow: interface → core → audio → LLM → speech

1. **Interface layer (`Nova/Interface.py`)**
   - Presents a text-based command menu using localized strings from `ConfigInteraction.GetLanguageFile()` (`LangFiles/*.json`).
   - `Boot()` computes the absolute path to `Nova/StartCore.py` and uses `subprocess.Popen` with `start cmd /c ...` to open a separate Windows terminal titled `Nova` and run `python StartCore.py`.
   - Settings and keys are edited interactively:
     - `Settings()` loads and persists `NovaSettings.config` via `ConfigInteraction` with per-field validation through `CheckForValidInput.CheckForValidInput`.
     - `EditAPIkeys()` enumerates key names from `KeyManager.GetKeyList()` and writes values using the system keyring (`keyring` library).
   - `ProcessInput()` loops reading commands (`help`, `boot`, `keys`, `settings`, `micID`, etc.) until `exit` is entered.

2. **Core engine (`Nova/Core.py` and `Nova/StartCore.py`)**
   - `StartCore.py` calls `Core.Start()`, which in turn:
     - Calls `Initialize()`, which initializes:
       - Audio transcription (`AudioTranscription.Initialize()`),
       - LLM backends (`LanguageModelInteraction.Initialize()`),
       - Speech synthesis (`SpeechSynthesis.Initialize()`),
       - Connectivity checks to Groq and Elevenlabs if `OfflineMode == "False"`.
     - Adds an initial system prompt (constructed from the `Behaviour` setting plus a hidden system prompt) to the conversation history.
     - Clears the console and prints a header with:
       - Version information from `manifest.json`,
       - Current behaviour string,
       - Online/offline/mixed mode status,
       - Count of valid and invalid modules from `ModuleManager.ScanModules()`.
   - Conversation state is kept in the `conversation` list, where entries are "user", "assistant", "system", or "function" messages.
   - `IdleLoop(tasks, results)` drives the runtime:
     - Dequeues commands (if running under `NovaAPI`), then
     - If `runHotwordDetection` is enabled, calls `AudioTranscription.DetectHotword()` in a loop.
     - When speech containing the hotword is transcribed, `AddToConversation()` adds a `"user"` message and triggers `CallLanguageModel()`.

3. **Transcription layer (`Nova/AudioTranscription.py`)**
   - Reads `MicrophoneIndex`, `Hotword`, `Language`, and `OfflineMode` from `NovaSettings.config` via `ConfigInteraction`.
   - `Initialize()` selects between cloud and local transcription:
     - Online / mixed modes: uses Groq’s `whisper-large-v3` via `Groq` client and `client.audio.transcriptions.create(...)`.
     - Offline mode: configures a local `faster-whisper` model (`distil-large-v3`) with CUDA.
   - Audio capture uses `sounddevice.InputStream`:
     - A callback maintains an in-memory buffer until silence exceeds a threshold, then writes `temp_audio.wav` and runs either `ProcessAPI()` or `ProcessLocal()`.
     - Simple VAD is performed via the `silero-vad` model loaded from `torch.hub` to avoid transcribing silence.
   - `DetectHotword()` calls `Listen()` and returns the full transcription only if the configured `Hotword` substring is present; otherwise it returns `None` and the core loop waits for another utterance.

4. **Language model layer (`Nova/LanguageModelInteraction.py`)**
   - Determines the backend from `OfflineMode` and settings:
     - **Online mode (`OfflineMode == "False"`)**
       - Instantiates a `Groq` client with the `Groq` key from `KeyManager`.
       - Reads the Groq model name (e.g. `llama3-70b-8192`) from `NovaSettings.config`.
       - Configures Google Gemini (`gemini-1.5-flash`) using the `Google Gemini` key (if present) for multimodal calls.
       - `PromptLanguageModelAPI()` calls `client.chat.completions.create(...)` with:
         - `messages` = the conversation plus system metadata (date, time, user name),
         - `tools` = converted module manifests from `ModuleManager.GetModules()`,
         - `stream` flag controlling server-side streaming.
     - **Offline mode (`OfflineMode != "False"`)**
       - Ensures a local Llama 3 GGUF is present under `Models/Llama3`; if missing, downloads `Meta-Llama-3-8B-Instruct-Q8_0.gguf` from the Hugging Face hub using `hf_hub_download`.
       - Instantiates `llama_cpp.Llama` with `chat_format="chatml"`, full GPU offload (`n_gpu_layers=-1`), and a 2048-token context window.
       - `PromptLanguageModelLocal()` calls `model.create_chat_completion(...)` on the in-memory conversation.
   - `LLMStreamProcessor` abstracts Groq streaming responses:
     - Iterates over the event stream, yielding content chunks for TTS while accumulating `response_text`.
     - Detects the first tool call (function call) and stops consuming after it to hand off execution to the module system.

5. **Speech synthesis layer (`Nova/SpeechSynthesis.py`)**
   - Reads `OfflineMode`, `ElevenlabsModel`, `ElevenlabsVoiceID`, and `StreamVoice` from `NovaSettings.config`.
   - **Online / mixed modes:**
     - Uses `elevenlabs` client with an API key from `KeyManager`.
     - `SpeakStream()` streams or plays audio directly from Elevenlabs depending on `StreamVoice`.
     - `SpeakDirect()` generates full audio before playback.
   - **Offline mode:**
     - Uses the `TTS` library (Coqui TTS) with a bundled English model (`tts_models/en/ljspeech/tacotron2-DDC`).
     - `SpeakOffline()` synthesizes to `output.wav`, plays via `simpleaudio`, then deletes the temporary file.

6. **Module system (`Nova/ModuleManager.py` and `Modules/`)**
   - Modules live as subdirectories under `Modules/`, each with:
     - A `manifest.json` describing one or more functions (`EntryScript`, `EntryFunction`, `ModuleName`, `ModuleDescription`, and `Parameters`).
     - The script referenced by `EntryScript`, which must define `EntryFunction` with a matching parameter count.
   - `CheckModuleValidity()` enforces basic structural constraints:
     - Manifest presence and required fields,
     - Existence of the entry script,
     - Function parameter count matching the manifest.
   - `GetModules()` transforms valid manifests into the OpenAI/Groq tools format for use in `client.chat.completions.create(...)`.
   - `CallFunction(name, parameters)` performs secure dynamic dispatch:
     - Applies a `RestrictedImporter` (from `Helpers.py`) that blocks imports of dangerous libraries (`os`, `sys`, `subprocess`, `keyring`, `KeyManager`).
     - Dynamically loads the module script and resolves the entry function.
     - Extracts ordered arguments from a parameters dict according to the manifest-specified `Parameters` list.
     - Calls the function and returns its return value (or `True` on success with no return value; `False` on general exceptions).
     - On attempted import of disallowed libraries, returns a high-priority security warning string instructing the model to alert the user.
   - The `Core` engine treats module returns as function/tool call results, appends them to the conversation as `"function"` messages, and, if any functions were invoked, re-calls the language model to integrate their outputs into a final assistant response.

7. **Configuration, localization, and key management**

- `Nova/ConfigInteraction.py` centralizes file-based configuration access:
  - `GetSetting` / `GetSettings` / `SetSettings` for `NovaSettings.config`.
  - Accessors for `InterfaceCommands.json`, `ModuleList.json`, `Functions.json`, `HasModuleBeenInitialized.json` (these support module and interface metadata, though not all are present in the current tree).
  - `GetManifest()` reads the root `manifest.json` for version and metadata.
  - `GetLanguageFile()` selects the appropriate language file under `LangFiles/` based on the `Language` setting, falling back to English (`en.json`) with an explicit error if missing.
- `Nova/KeyManager.py` abstracts API key storage:
  - Uses the `keyring` library to store and retrieve secrets under the "Nova" service name.
  - Relies on `Nova/Configs/KeyList.json` to enumerate logical key labels (e.g. `"Groq"`, `"Elevenlabs"`).
- `Nova/CheckForValidInput.py` validates user input for settings:
  - Language codes are validated via `langcodes.Language`.
  - Elevenlabs voice IDs are optionally checked via `client.voices.get(...)`.
  - Boolean-like fields (`OfflineMode`, `StreamVoice`) are constrained to enumerated strings.
  - `MicrophoneIndex` must be an integer.

8. **Programmatic API (`NovaAPI.py`)**

The file `NovaAPI.py` exposes a thin, queue-based API for embedding Nova into other Python programs:

- Starts Nova in a background thread (`Core.StartFromAPI`) with shared mutable `novaStatus` and `Queue` objects for tasks and results.
- Exposes methods to:
  - `SetSetting(name, value)` / `GetSetting(name)` — directly manipulate settings in `NovaSettings.config` with validation.
  - `SetKey(name, value)` / `GetKey(name)` — manage secrets via `KeyManager`.
  - `StartNova(hotword: bool)` / `StopNova()` — control the lifecycle of the core engine.
  - `GetStatus()` — read the current status flag (0 = stopped, 1 = ready, 2 = initializing, by convention in `Core.StartFromAPI`).
  - `AddToConversation(role, content)`, `GetConversation()`, `SetConversation(conversation)` — manipulate the internal conversation history.
  - `RunWithSpeech()` — ask the model a question using the current conversation and speak the result.
  - `Run()` — same, but returns text only.
  - `ToggleHotwordDetection(detect)` and `Speak(text)` — control hotword usage and trigger speech synthesis directly.

When extending or refactoring the API, preserve the queue-based contract with the core (`tasks` and `results` queues) and the task names recognized by `Core.DequeueTask()`.

## Security model and module safety

Security for third-party modules is implemented at two levels:

- **Structural validation**: module manifests and entry functions must conform to the expected shape (manifest fields populated, parameter counts matching function signatures). Invalid modules are counted and surfaced in the core header.
- **Import-time sandboxing**: `Helpers.RestrictedImporter` intercepts imports to block known-dangerous libraries for modules (`os`, `sys`, `subprocess`, `keyring`, `KeyManager`). Attempts to import these produce a deterministic security-warning return string that the LLM is expected to surface to the user.

The README emphasizes that this protection is partial and that users should manually review third-party modules. Any changes to the module system should maintain or improve this safety posture and keep security warnings user-visible via the conversation flow.
