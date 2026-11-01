@echo off
setlocal
cd /d "%~dp0"
echo This downloads the free Qwen3 1.7B model, about 1.4 GB, through Ollama.
echo Open Ollama first. No business documents are sent by this command.
ollama pull qwen3:1.7b
if errorlevel 1 (
  echo Installation did not finish. Open Ollama and try again.
) else (
  echo Model installed. Open Own and choose Check again in AI connection.
)
pause
