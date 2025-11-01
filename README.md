# demo-fast
Lightweight demo environment for AI red-team showcase (fraud ML, LLM via Ollama, Agent, prompt tests).

Quick start (local):

1. Install Ollama on the host and pull a small model (e.g., gemma2).
   - https://ollama.ai (follow installer for your OS)
   - ollama pull gemma2
2. Install garak:
   ```bash
   pip install --force-reinstall "garak==0.12.0"
   ```
3. Build and run demo:
   ```bash
   docker-compose up --build
   ```
4. Access services:
   - Fraud model predict: http://localhost:5001/predict
   - LLM proxy: http://localhost:5002/generate
   - Agent chat: http://localhost:5003/chat
5. Run ART demo inside fraud container:
   ```bash
   docker exec -it demo_fraud python art_attack_demo.py
   ```

Notes:
- All data is synthetic and simulated. Do NOT use real PII.
- The llm proxy uses Ollama by default. If Ollama is not available, the proxy can be adjusted to demo-mode returning deterministic responses.
