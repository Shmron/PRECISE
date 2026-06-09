#!/bin/bash
cd /home/rutendo/PRECISE/palsearth
/opt/anaconda3/bin/streamlit run app.py \
  --server.port 8503 \
  --server.baseUrlPath /palsearth \
  --server.address 127.0.0.1 \
  --server.headless true \
  --server.enableCORS false \
  --server.enableXsrfProtection false
