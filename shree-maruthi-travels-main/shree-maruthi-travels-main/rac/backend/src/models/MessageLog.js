import { DataTypes } from 'sequelize';
import sequelize from '../config/database.js';

const MessageLog = sequelize.define('message_log', {
  message_log_id: {
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
  assignment_id: {
    type: DataTypes.UUID,
    allowNull: true,
    references: {
      model: 'assignments',
      key: 'assignment_id'
    }
  },
  phone_number: {
    type: DataTypes.STRING(20),
    allowNull: false
  },
  message_body: {
    type: DataTypes.TEXT,
    allowNull: false
  },
  provider_name: {
    type: DataTypes.STRING(50),
    allowNull: false
  },
  provider_msg_id: {
    type: DataTypes.STRING(100),
    allowNull: true
  },
  send_status: {
    type: DataTypes.ENUM('pending', 'sent', 'failed', 'queued'),
    defaultValue: 'pending',
    allowNull: false
  },
  delivery_status: {
    type: DataTypes.ENUM('queued', 'sent', 'delivered', 'read', 'failed'),
    allowNull: true
  },
  sent_at: {
    type: DataTypes.DATE,
    allowNull: true
  },
  delivered_at: {
    type: DataTypes.DATE,
    allowNull: true
  },
  read_at: {
    type: DataTypes.DATE,
    allowNull: true
  },
  failed_reason: {
    type: DataTypes.TEXT,
    allowNull: true
  },
  retry_count: {
    type: DataTypes.INTEGER,
    defaultValue: 0
  }
}, {
  tableName: 'message_logs',
  timestamps: true,
  underscored: true
});

export default MessageLog;
