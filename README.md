# Media Intelligence & Security Monitoring API

A production-grade FastAPI application that monitors news and social media for
specific targets (people, companies, brands), providing sentiment analysis,
security threat detection, and risk assessment.

---

## Architecture

**Request Flow:**

    Client Request
         |
         v
    +---------------+     +----------------+     +----------------+
    |    FastAPI     |---->|    Services    |---->|    Database    |
    |  Controllers   |     | (Bus. Logic)   |     |  (PostgreSQL)  |
    +---------------+     +-------+--------+     +----------------+
                                  |
                          +-------v--------+
                          |     Agents     |
                          | (Multi-Agent)  |
                          +----------------+
                            |    |    |
                        Search Scrape Analysis
                        Agent  Agent  Agent

### MVC Pattern

| Layer           | Location         | Responsibility                            |
|-----------------|------------------|-------------------------------------------|
| **Controllers** | `app/api/`       | HTTP request/response handling             |
| **Services**    | `app/services/`  | Business logic, validation, orchestration  |
| **Models**      | `app/models/`    | SQLAlchemy ORM definitions                 |
| **Schemas**     | `app/schemas/`   | Pydantic request/response models           |
| **Agents**      | `app/agents/`    | AI/scraping pipeline                       |
| **Core**        | `app/core/`      | Config, auth, DB, logging, utilities       |

---

## Quick Start (Google Colab)

### 1. Install Dependencies

Run the setup cell to install PostgreSQL and Python packages.

### 2. Configure Environment

Set your API keys in the `.env` cell.

### 3. Start the Server

Run the server cell:

    !python run.py

### 4. Access the API

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc
- **Health Check:** http://localhost:8000/health

---

## Authentication

### Register

    curl -X POST http://localhost:8000/api/v1/auth/register \
      -H "Content-Type: application/json" \
      -d '{"email": "user@example.com", "password": "MyP@ssw0rd!", "full_name": "John Doe"}'

### Login

    curl -X POST http://localhost:8000/api/v1/auth/login \
      -H "Content-Type: application/json" \
      -d '{"email": "user@example.com", "password": "MyP@ssw0rd!"}'

### Use Token

    curl -X GET http://localhost:8000/api/v1/users/me \
      -H "Authorization: Bearer <access_token>"

---

## API Endpoints

### Auth — `/api/v1/auth`

| Method | Endpoint      | Description            | Access |
|--------|---------------|------------------------|--------|
| POST   | `/register`   | Register new user      | Public |
| POST   | `/login`      | Login & get JWT tokens | Public |
| POST   | `/refresh`    | Refresh access token   | Auth   |
| POST   | `/logout`     | Revoke refresh token   | Auth   |

### Users — `/api/v1/users`

| Method | Endpoint       | Description        | Access |
|--------|----------------|--------------------|--------|
| GET    | `/me`          | Get own profile    | User+  |
| PUT    | `/me`          | Update own profile | User+  |
| GET    | `/`            | List all users     | Admin  |
| GET    | `/{user_id}`   | Get user by ID     | Admin  |
| PUT    | `/{user_id}`   | Update any user    | Admin  |
| DELETE | `/{user_id}`   | Deactivate user    | Admin  |

### Targets — `/api/v1/targets`

| Method | Endpoint         | Description        | Access |
|--------|------------------|--------------------|--------|
| POST   | `/`              | Create/link target | User+  |
| GET    | `/`              | List own targets   | User+  |
| GET    | `/{target_id}`   | Get target details | User+  |
| PUT    | `/{target_id}`   | Update target      | Admin  |
| DELETE | `/{target_id}`   | Delete target      | Admin  |

### Scans — `/api/v1/scans`

| Method | Endpoint                | Description           | Access |
|--------|-------------------------|-----------------------|--------|
| POST   | `/`                     | Create scan           | User+  |
| GET    | `/`                     | List own scans        | User+  |
| GET    | `/scheduled`            | List scheduled scans  | User+  |
| GET    | `/{scan_id}`            | Get scan details      | User+  |
| DELETE | `/{scan_id}/schedule`   | Cancel scheduled scan | User+  |

### Results — `/api/v1/results`

| Method | Endpoint                | Description        | Access |
|--------|-------------------------|--------------------|--------|
| GET    | `/target/{target_id}`   | Get target results | User+  |
| GET    | `/scan/{scan_id}`       | Get scan results   | User+  |

---

## Target Name Normalization

Target names are automatically normalized for deduplication:

- `"John Doe"`, `"john doe"`, `"JOHN DOE"` all resolve to the **same target**
- `"Jose Garcia"` is the normalized form of `"José García"`
- Multiple users can share the same target seamlessly

---

## Scan Types

### One-Time Scan

Executes immediately upon creation, stores results in the database, and is
marked as `completed`.

### Scheduled Scan

Runs at user-defined intervals (e.g., every N hours, days, or weeks). Schedule
definitions persist across application restarts. Users can cancel anytime while
all historical results are preserved.

---

## Security Features

- **JWT access + refresh tokens** for stateless authentication
- **bcrypt password hashing** via passlib
- **Role-based access control** with admin and user roles
- **Rate limiting** on authentication endpoints
- **Input validation** on all endpoints via Pydantic

---

## Project Structure

    app/
    ├── core/              # Config, DB, auth, logging, utilities
    │   ├── config.py      # Environment-based settings
    │   ├── database.py    # Async engine & session factory
    │   ├── security.py    # JWT & password utilities
    │   └── logging.py     # Structured logging setup
    ├── models/            # SQLAlchemy ORM models
    │   ├── user.py        # User model with roles
    │   ├── target.py      # Target with normalized names
    │   ├── scan.py        # Scan & schedule definitions
    │   ├── article.py     # Scraped article storage
    │   └── scan_result.py # Scan-to-article junction
    ├── schemas/           # Pydantic request/response models
    │   ├── auth.py        # Login, token schemas
    │   ├── user.py        # User CRUD schemas
    │   ├── target.py      # Target schemas
    │   ├── scan.py        # Scan schemas
    │   └── article.py     # Article/result schemas
    ├── services/          # Business logic layer
    │   ├── auth_service.py
    │   ├── user_service.py
    │   ├── target_service.py
    │   ├── scan_service.py
    │   ├── scheduler_service.py
    │   └── result_service.py
    ├── agents/            # Multi-agent AI pipeline
    │   ├── orchestrator.py
    │   ├── scrapers/
    │   │   ├── base_scraper.py
    │   │   ├── news_api_scraper.py
    │   │   └── google_scraper.py
    │   └── processors/
    │       ├── deduplicator.py
    │       └── normalizer.py
    ├── api/
    │   ├── v1/            # API v1 route controllers
    │   │   ├── auth.py
    │   │   ├── users.py
    │   │   ├── targets.py
    │   │   ├── scans.py
    │   │   └── results.py
    │   ├── dependencies.py
    │   └── health.py
    └── main.py            # FastAPI app factory

---

## Default Admin Credentials

| Field    | Value                  |
|----------|------------------------|
| Email    | `admin@mediaintel.com` |
| Password | `Admin@123!`           |

> **WARNING:** Change these credentials immediately in production!

---

## Environment Variables

    DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/mediaintel
    SECRET_KEY=your-secret-key-here
    ALGORITHM=HS256
    ACCESS_TOKEN_EXPIRE_MINUTES=30
    REFRESH_TOKEN_EXPIRE_DAYS=7
    NEWS_API_KEY=your-news-api-key
    GOOGLE_API_KEY=your-google-api-key
    GOOGLE_CSE_ID=your-custom-search-engine-id
    DEFAULT_ADMIN_EMAIL=admin@mediaintel.com
    DEFAULT_ADMIN_PASSWORD=Admin@123!
    LOG_LEVEL=INFO

---

## License

This project is for internal use. All rights reserved.
