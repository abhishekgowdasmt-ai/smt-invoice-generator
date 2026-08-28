-- Dispatch Management System Database Schema
-- Phase 1 MVP

-- Table 1: Users
CREATE TABLE IF NOT EXISTS users (
  user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  phone_number VARCHAR(20),
  password_hash VARCHAR(255) NOT NULL,
  first_name VARCHAR(100),
  last_name VARCHAR(100),
  role VARCHAR(50) NOT NULL DEFAULT 'staff' CHECK (role IN ('admin', 'staff', 'view_only')),
  active BOOLEAN NOT NULL DEFAULT true,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  last_login_at TIMESTAMP
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_active ON users(active);
CREATE INDEX idx_users_role ON users(role);

-- Table 2: Drivers (MUST be before bookings)
CREATE TABLE IF NOT EXISTS drivers (
  driver_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  driver_name VARCHAR(200) NOT NULL,
  whatsapp_number VARCHAR(20) UNIQUE NOT NULL,
  alternate_number VARCHAR(20),
  vehicle_number VARCHAR(50),
  vehicle_type VARCHAR(50),
  home_area VARCHAR(100),
  active_status BOOLEAN NOT NULL DEFAULT true,
  total_assignments INTEGER DEFAULT 0,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_drivers_whatsapp_number ON drivers(whatsapp_number);
CREATE INDEX idx_drivers_driver_name ON drivers(driver_name);
CREATE INDEX idx_drivers_vehicle_number ON drivers(vehicle_number);
CREATE INDEX idx_drivers_active_status ON drivers(active_status);

-- Table 3: Upload Batches
CREATE TABLE IF NOT EXISTS upload_batches (
  batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  file_name VARCHAR(255) NOT NULL,
  file_path VARCHAR(500),
  file_size BIGINT,
  uploaded_by UUID NOT NULL REFERENCES users(user_id),
  uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  total_rows INTEGER NOT NULL,
  success_rows INTEGER DEFAULT 0,
  failed_rows INTEGER DEFAULT 0,
  import_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (import_status IN ('pending', 'completed', 'failed')),
  error_summary JSONB,
  notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_upload_batches_uploaded_by ON upload_batches(uploaded_by);
CREATE INDEX idx_upload_batches_uploaded_at ON upload_batches(uploaded_at);
CREATE INDEX idx_upload_batches_import_status ON upload_batches(import_status);

-- Table 4: Bookings/Rides (now can reference both drivers and upload_batches)
CREATE TABLE IF NOT EXISTS bookings (
  booking_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source_booking_id VARCHAR(50) UNIQUE,
  sl_no INTEGER,
  trip_date DATE NOT NULL,
  vendor_name VARCHAR(200),
  source_name VARCHAR(200),
  source_mobile VARCHAR(20),
  source_vehicle_no VARCHAR(50),
  planned_start VARCHAR(100),
  route_text TEXT,
  pickup_time TIME,
  end_time TIME,
  total_hours_text VARCHAR(50),
  cab_type VARCHAR(50),
  employee_name VARCHAR(200) NOT NULL,
  start_km DECIMAL(8,2),
  end_km DECIMAL(8,2),
  total_km DECIMAL(8,2),
  duty_type VARCHAR(100),
  driver_hours DECIMAL(5,2),
  driver_km DECIMAL(8,2),
  toll DECIMAL(10,2) DEFAULT 0,
  parking DECIMAL(10,2) DEFAULT 0,
  amount DECIMAL(10,2) NOT NULL,
  remarks TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'Uploaded' CHECK (status IN ('Uploaded', 'Unassigned', 'Assigned', 'Message Sent', 'Message Failed', 'Completed', 'Cancelled')),
  upload_batch_id UUID NOT NULL REFERENCES upload_batches(batch_id),
  assigned_driver_id UUID REFERENCES drivers(driver_id) ON DELETE SET NULL,
  assigned_at TIMESTAMP,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_bookings_source_booking_id ON bookings(source_booking_id);
CREATE INDEX idx_bookings_trip_date ON bookings(trip_date);
CREATE INDEX idx_bookings_status ON bookings(status);
CREATE INDEX idx_bookings_assigned_driver_id ON bookings(assigned_driver_id);
CREATE INDEX idx_bookings_upload_batch_id ON bookings(upload_batch_id);
CREATE INDEX idx_bookings_employee_name ON bookings(employee_name);

-- Table 5: Assignments
CREATE TABLE IF NOT EXISTS assignments (
  assignment_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id UUID NOT NULL REFERENCES bookings(booking_id),
  driver_id UUID NOT NULL REFERENCES drivers(driver_id),
  assigned_by UUID NOT NULL REFERENCES users(user_id),
  assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  whatsapp_message_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (whatsapp_message_status IN ('pending', 'sent', 'failed', 'delivered')),
  whatsapp_message_id VARCHAR(100),
  whatsapp_sent_at TIMESTAMP,
  whatsapp_delivery_status VARCHAR(50) CHECK (whatsapp_delivery_status IN ('queued', 'sent', 'delivered', 'read', 'failed')),
  assignment_notes TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_assignments_booking_id ON assignments(booking_id);
CREATE INDEX idx_assignments_driver_id ON assignments(driver_id);
CREATE INDEX idx_assignments_assigned_by ON assignments(assigned_by);
CREATE INDEX idx_assignments_assigned_at ON assignments(assigned_at);
CREATE INDEX idx_assignments_whatsapp_message_status ON assignments(whatsapp_message_status);

-- Table 6: Message Logs
CREATE TABLE IF NOT EXISTS message_logs (
  message_log_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  booking_id UUID NOT NULL REFERENCES bookings(booking_id),
  driver_id UUID NOT NULL REFERENCES drivers(driver_id),
  assignment_id UUID REFERENCES assignments(assignment_id),
  phone_number VARCHAR(20) NOT NULL,
  message_body TEXT NOT NULL,
  provider_name VARCHAR(50) NOT NULL,
  provider_msg_id VARCHAR(100),
  send_status VARCHAR(50) NOT NULL DEFAULT 'pending' CHECK (send_status IN ('pending', 'sent', 'failed', 'queued')),
  delivery_status VARCHAR(50) CHECK (delivery_status IN ('queued', 'sent', 'delivered', 'read', 'failed')),
  sent_at TIMESTAMP,
  delivered_at TIMESTAMP,
  read_at TIMESTAMP,
  failed_reason TEXT,
  retry_count INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_message_logs_booking_id ON message_logs(booking_id);
CREATE INDEX idx_message_logs_driver_id ON message_logs(driver_id);
CREATE INDEX idx_message_logs_phone_number ON message_logs(phone_number);
CREATE INDEX idx_message_logs_send_status ON message_logs(send_status);
CREATE INDEX idx_message_logs_delivery_status ON message_logs(delivery_status);
CREATE INDEX idx_message_logs_sent_at ON message_logs(sent_at);

-- Table 7: Audit Logs
CREATE TABLE IF NOT EXISTS audit_logs (
  audit_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  action_type VARCHAR(50) NOT NULL CHECK (action_type IN ('login', 'upload', 'create', 'assign', 'send', 'delete', 'update')),
  entity_type VARCHAR(50) NOT NULL,
  entity_id VARCHAR(100),
  action_by UUID NOT NULL REFERENCES users(user_id),
  old_values JSONB,
  new_values JSONB,
  ip_address VARCHAR(50),
  user_agent TEXT,
  status VARCHAR(50) NOT NULL DEFAULT 'success' CHECK (status IN ('success', 'failure')),
  error_message TEXT,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_logs_action_type ON audit_logs(action_type);
CREATE INDEX idx_audit_logs_entity_type ON audit_logs(entity_type);
CREATE INDEX idx_audit_logs_action_by ON audit_logs(action_by);
CREATE INDEX idx_audit_logs_created_at ON audit_logs(created_at);
