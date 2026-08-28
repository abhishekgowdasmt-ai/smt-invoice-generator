import { DataTypes } from 'sequelize';
import sequelize from '../config/database.js';
import Driver from './Driver.js';

const Booking = sequelize.define('booking', {
  booking_id: {
    type: DataTypes.UUID,
    defaultValue: DataTypes.UUIDV4,
    primaryKey: true
  },
  source_booking_id: {
    type: DataTypes.STRING(50),
    unique: true,
    allowNull: true
  },
  sl_no: {
    type: DataTypes.INTEGER,
    allowNull: true
  },
  trip_date: {
    type: DataTypes.DATEONLY,
    allowNull: false
  },
  vendor_name: {
    type: DataTypes.STRING(200),
    allowNull: true
  },
  source_name: {
    type: DataTypes.STRING(200),
    allowNull: true
  },
  source_mobile: {
    type: DataTypes.STRING(20),
    allowNull: true
  },
  source_vehicle_no: {
    type: DataTypes.STRING(50),
    allowNull: true
  },
  planned_start: {
    type: DataTypes.STRING(100),
    allowNull: true
  },
  route_text: {
    type: DataTypes.TEXT,
    allowNull: true
  },
  pickup_time: {
    type: DataTypes.TIME,
    allowNull: true
  },
  end_time: {
    type: DataTypes.TIME,
    allowNull: true
  },
  total_hours_text: {
    type: DataTypes.STRING(50),
    allowNull: true
  },
  cab_type: {
    type: DataTypes.STRING(50),
    allowNull: true
  },
  employee_name: {
    type: DataTypes.STRING(200),
    allowNull: false
  },
  start_km: {
    type: DataTypes.DECIMAL(8, 2),
    allowNull: true
  },
  end_km: {
    type: DataTypes.DECIMAL(8, 2),
    allowNull: true
  },
  total_km: {
    type: DataTypes.DECIMAL(8, 2),
    allowNull: true
  },
  duty_type: {
    type: DataTypes.STRING(100),
    allowNull: true
  },
  driver_hours: {
    type: DataTypes.DECIMAL(5, 2),
    allowNull: true
  },
  driver_km: {
    type: DataTypes.DECIMAL(8, 2),
    allowNull: true
  },
  toll: {
    type: DataTypes.DECIMAL(10, 2),
    defaultValue: 0
  },
  parking: {
    type: DataTypes.DECIMAL(10, 2),
    defaultValue: 0
  },
  amount: {
    type: DataTypes.DECIMAL(10, 2),
    allowNull: false
  },
  remarks: {
    type: DataTypes.TEXT,
    allowNull: true
  },
  status: {
    type: DataTypes.ENUM('Uploaded', 'Unassigned', 'Assigned', 'Message Sent', 'Message Failed', 'Completed', 'Cancelled'),
    defaultValue: 'Uploaded',
    allowNull: false
  },
  upload_batch_id: {
    type: DataTypes.UUID,
    allowNull: false,
    references: {
      model: 'upload_batches',
      key: 'batch_id'
    }
  },
  assigned_driver_id: {
    type: DataTypes.UUID,
    allowNull: true,
    references: {
      model: 'drivers',
      key: 'driver_id'
    }
  },
  assigned_at: {
    type: DataTypes.DATE,
    allowNull: true
  }
}, {
  tableName: 'bookings',
  timestamps: true,
  underscored: true
});

// Define association
Booking.belongsTo(Driver, {
  foreignKey: 'assigned_driver_id',
  as: 'assignedDriver'
});

export default Booking;
