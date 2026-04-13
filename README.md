
# GDrive Sync API

It's all about API endpoints built with FastAPI. The API centers around some Python scripts and it tracks and posts activity statuses accustomed to those scripts.


## Tech Stack

**Client:** Python scripts

**Server:** FastAPI


## Features

- Public and protected routes with RBAC
- JWT, Bearer tokens implementation
- Cutom log and state files to track errors and previous activities
- API versioning capabled


## Documentation

- Swagger generated [Documentation - http://localhost:8000/docs](http://localhost:8000/docs)


## Environment Variables

To run this project, you will need to add the following environment variables to your .env file

`RCLONE_EXE` `LOG_FILE` `STATE_FILE` `MAX_UPLOAD_WORKERS` `SETTLE_SECONDS` `DIALOG_TIMEOUT` `LOG_MAX_MB` `LOG_BACKUPS` `ADMIN_PASSWORD` `VIEWER_PASSWORD` `JWT_SECRET` `JWT_EXPIRE_MINUTES` `CORS_ORIGINS`


## Running Tests

To run tests, run the following command

```bash
  pytest tests/ -v
```
Note: Tests use the FastAPI TestClient (HTTPX) and mock the sync engine
state directly — no Rclone or filesystem access needed.

