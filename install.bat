@echo off

:: Create python environment
python -m venv venv
call venv\Scripts\activate
if exist requirements.txt pip install -r requirements.txt

:: Create environment file
(
	echo # Hosting addresses
	echo HOST_ADDRESS=127.0.0.1
	echo
	echo # Connectivity
	echo WEBSOCKET_PORT=49170
	echo
	echo # Models run slightly faster, like 5-10%
	echo GGML_CUDA_GRAPH_OPT=1
) > .env


:: Make vendor directory
if not exist .\vendor mkdir .\vendor
cd .\vendor
if not exist .\bin mkdir .\bin

:: Download and install llama.cpp
git clone https://github.com/ggml-org/llama.cpp.git

cd .\llama.cpp
cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="86" -DGGML_CUDA_F16=ON -DGGML_CUDA_FORCE_MMQ=ON -DGGML_CUDA_PEER_MAX_BATCH_SIZE=1 -DLLAMA_CURL=OFF -DGGML_NATIVE=ON
cmake --build build --config Release --target llama-bench --target llama-perplexity --target llama-quantize --target llama-server --parallel
robocopy .\build\bin\Release ..\bin\llama.cpp /E
cd ..\

:: Download and install whisper.cpp
git clone https://github.com/ggml-org/whisper.cpp.git

:: We use custom server code
cd .\whisper.cpp\examples
rmdir /s /q server
git clone https://github.com/Emma-Kyu/Whisper-Server-Code.git server
cd ..\

cmake -B build -DGGML_CUDA=ON -DCMAKE_CUDA_ARCHITECTURES="86" -DGGML_CUDA_F16=ON -DGGML_CUDA_FORCE_MMQ=ON -DGGML_NATIVE=ON
cmake --build build -j --config Release --parallel
robocopy .\build\bin\Release ..\bin\whisper.cpp /E
cd ..\..\