#!/bin/bash
set -e

PGDATA="/var/lib/postgresql/data"
PGUSER="${POSTGRES_USER:-postgres}"
PGPASSWORD="${POSTGRES_PASSWORD:-postgres}"
PGDB="${POSTGRES_DB:-media_intel}"

# Initialize DB if not already done
if [ ! -f "$PGDATA/PG_VERSION" ]; then
    echo "[postgres] Initializing database cluster..."
    gosu postgres /usr/lib/postgresql/*/bin/initdb -D "$PGDATA" --auth=md5 --username="$PGUSER"
    
    # Start postgres temporarily to set password and create DB
    gosu postgres /usr/lib/postgresql/*/bin/pg_ctl -D "$PGDATA" -o "-c listen_addresses=''" -w start
    
    gosu postgres psql -c "ALTER USER $PGUSER WITH PASSWORD '$PGPASSWORD';"
    gosu postgres psql -c "CREATE DATABASE $PGDB OWNER $PGUSER;" 2>/dev/null || true
    
    gosu postgres /usr/lib/postgresql/*/bin/pg_ctl -D "$PGDATA" -m fast -w stop
    echo "[postgres] Initialization complete."
fi

# Update pg_hba.conf to allow password auth
echo "host all all 127.0.0.1/32 md5" >> "$PGDATA/pg_hba.conf"
echo "host all all ::1/128 md5" >> "$PGDATA/pg_hba.conf"

echo "[postgres] Starting PostgreSQL..."
exec gosu postgres /usr/lib/postgresql/*/bin/postgres -D "$PGDATA" -c listen_addresses='127.0.0.1'
