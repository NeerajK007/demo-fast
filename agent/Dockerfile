# ---------- Base Image ----------
  FROM python:3.11-slim

  # ---------- Working Directory ----------
  WORKDIR /app
  
  # ---------- Copy Project ----------
  COPY . /app
  
  # ---------- Install Dependencies ----------
  RUN pip install --no-cache-dir -r requirements.txt
  
  # ---------- Environment Variables ----------
  # These can be overridden at runtime via docker-compose.yml or `docker run -e`
  ENV PYTHONUNBUFFERED=1 \
      LLM_URL=http://localhost:5002/generate \
      DATA_PATH=/app/data/customers_transactions.json \
      AUTO_EXECUTE=true \
      RED_TEAM_MODE=false
  
  # ---------- Expose Port ----------
  EXPOSE 5003
  
  # ---------- Entrypoint ----------
  CMD ["python", "-u", "agent_server.py"]
  