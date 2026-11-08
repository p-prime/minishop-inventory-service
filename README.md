# MiniShop Inventory Service
Python 3.12. From this repository directory:
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.lock
python -m pytest -q
python -m uvicorn app.main:app --port 8001
```
Linux activation: `source .venv/bin/activate`.
Open http://localhost:8001/docs and /openapi.json. Read API.md.
The default SQLite file is created in the current directory. Set DATABASE_URL to a writable file. Order requires INVENTORY_URL, default http://localhost:8001.
Build: `docker build -t minishop-inventory:1.0 .`
Standalone Docker: `docker run --rm -p 8001:8001 -v inventory-data:/data minishop-inventory:1.0`.
For Order container communication use the integration Compose file; localhost in a container is that container.
Kubernetes: create namespace `minishop`, load image, apply `k8s/service.yaml`; full sequence in integration/README.md in the submission package.
No license grant is asserted for this academic submission. Dependencies retain their own licenses.
