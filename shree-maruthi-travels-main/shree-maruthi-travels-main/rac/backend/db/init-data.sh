#!/bin/bash
set -e

# This script runs when PostgreSQL starts for the first time
# It creates all tables and inserts initial data

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    -- Insert test admin user
    INSERT INTO users (email, password_hash, first_name, last_name, role, active)
    VALUES ('admin@dispatch.local', '\$2b\$10\$n1DvHxwrXoa29J7kcNMaT.VyQCRDSYMWhf7hLWmHH0zDpKuCJUHdy', 'Admin', 'User', 'admin', true)
    ON CONFLICT (email) DO NOTHING;

    -- Insert sample drivers
    INSERT INTO drivers (driver_name, whatsapp_number, vehicle_number, vehicle_type, home_area, active_status)
    VALUES 
      ('Rajesh Kumar', '+919876543210', 'HR26AB1234', 'SEDAN', 'Gurgaon', true),
      ('Amit Singh', '+919876543211', 'HR26AB1235', 'SUV', 'Noida', true),
      ('Priya Sharma', '+919876543212', 'HR26AB1236', 'TEMPO', 'Delhi', true)
    ON CONFLICT (whatsapp_number) DO NOTHING;
EOSQL
