import { DataTypes } from 'sequelize';
import sequelize from '../config/database.js';

const Driver = sequelize.define('driver', {
  driver_id: {
    type: DataTypes.UUID,
    defaultValue: DataTypes.UUIDV4,
    primaryKey: true
  },
  driver_name: {
    type: DataTypes.STRING(200),
    allowNull: false
  },
  whatsapp_number: {
    type: DataTypes.STRING(20),
    allowNull: false,
    unique: true
  },
  alternate_number: {
    type: DataTypes.STRING(20),
    allowNull: true
  },
  vehicle_number: {
    type: DataTypes.STRING(50),
    allowNull: true
  },
  vehicle_type: {
    type: DataTypes.STRING(50),
    allowNull: true
  },
  home_area: {
    type: DataTypes.STRING(100),
    allowNull: true
  },
  active_status: {
    type: DataTypes.BOOLEAN,
    defaultValue: true,
    allowNull: false
  },
  total_assignments: {
    type: DataTypes.INTEGER,
    defaultValue: 0
  },
  notes: {
    type: DataTypes.TEXT,
    allowNull: true
  }
}, {
  tableName: 'drivers',
  timestamps: true,
  underscored: true
});

export default Driver;
