#!/bin/bash
# Простий скрипт запуску pipeline на RunPod без Docker

set -e

echo "🚀 Starting Hyperrealistic Face Enhancement Pipeline..."

# Перевіряємо наявність Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 not found. Installing..."
    apt-get update && apt-get install -y python3 python3-pip
fi

# Перевіряємо наявність pip
if ! command -v pip3 &> /dev/null; then
    echo "❌ pip3 not found. Installing..."
    apt-get install -y python3-pip
fi

# Встановлюємо залежності
echo "📦 Installing dependencies..."
pip3 install -r /workspace/hyperrealistic/environment.yml

# Створюємо директорії
echo "📁 Creating directories..."
mkdir -p /workspace/data/input /workspace/data/outputs /workspace/logs

# Запускаємо WebUI
echo "🌐 Starting WebUI..."
cd /workspace/hyperrealistic
python3 pipelines/start_webui.py &
WEBUI_PID=$!

# Чекаємо WebUI
echo "⏳ Waiting for WebUI..."
for i in {1..60}; do
    if curl -s http://localhost:7860 > /dev/null; then
        echo "✅ WebUI is ready!"
        break
    fi
    if [ $i -eq 60 ]; then
        echo "❌ WebUI failed to start"
        exit 1
    fi
    sleep 5
done

# Запускаємо pipeline
echo "🎨 Starting face enhancement..."
python3 pipelines/process_faces.py --model realistic_vision --per-image 1
python3 pipelines/process_faces.py --model cinematic_beauty --per-image 1

# Аналізуємо результати
echo "📊 Analyzing results..."
python3 pipelines/compare_results.py --output-dir /workspace/data/outputs

echo "✅ Pipeline completed! WebUI remains running."
wait $WEBUI_PID
