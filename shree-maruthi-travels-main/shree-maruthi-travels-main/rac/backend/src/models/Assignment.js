import { DataTypes } from 'sequelize';
import sequelize from '../config/database.js';

const Assignment = sequelize.define('assignment', {
  assignment_id: {
    type: DataTypes.UUID,
    defaultValue: DataTypes.UUIDV4,
    primaryKey: true
  },
  booking_id: {
    type: DataTypes.UUID,
    allowNull: false,
    references: {
      model: 'bookings',
      key: 'booking_id'
    }
  },
  driver_id: {
    type: DataTypes.UUID,
    allowNull: false,
    references: {
      model: 'drivers',
      key: 'driver_id'
    }
  },
  assigned_by: {
    type: DataTypes.UUID,
    allowNull: false,
    references: {
      model: 'users',
      key: 'user_id'
    }
  },
  assigned_at: {
    type: DataTypes.DATE,
    defaultValue: DataTypes.NOW
  },
  whatsapp_message_status: {
    type: DataTypes.ENUM('pending', 'queued', 'sent', 'failed', 'delivered'),
    defaultValue: 'pending',
    allowNull: false
  },
  whatsapp_message_id: {
    type: DataTypes.STRING(100),
    allowNull: true
  },
  whatsapp_sent_at: {
    type: DataTypes.DATE,
    allowNull: true
  },
  whatsapp_delivery_status: {
    type: DataTypes.ENUM('queued', 'sent', 'delivered', 'read', 'failed'),
    allowNull: true
  },
  assignment_notes: {
    type: DataTypes.TEXT,
    allowNull: true
  }
}, {
  tableName: 'assignments',
  timestamps: true,
  underscored: true
});

export default Assignment;
