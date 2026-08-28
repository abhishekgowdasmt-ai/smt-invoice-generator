import { DataTypes } from 'sequelize';
import sequelize from '../config/database.js';

const UploadBatch = sequelize.define('upload_batch', {
  batch_id: {
    type: DataTypes.UUID,
    defaultValue: DataTypes.UUIDV4,
    primaryKey: true
  },
  file_name: {
    type: DataTypes.STRING(255),
    allowNull: false
  },
  file_path: {
    type: DataTypes.STRING(500),
    allowNull: true
  },
  file_size: {
    type: DataTypes.BIGINT,
    allowNull: true
  },
  uploaded_by: {
    type: DataTypes.UUID,
    allowNull: false,
    references: {
      model: 'users',
      key: 'user_id'
    }
  },
  total_rows: {
    type: DataTypes.INTEGER,
    allowNull: false
  },
  success_rows: {
    type: DataTypes.INTEGER,
    defaultValue: 0
  },
  failed_rows: {
    type: DataTypes.INTEGER,
    defaultValue: 0
  },
  import_status: {
    type: DataTypes.ENUM('pending', 'completed', 'failed'),
    defaultValue: 'pending',
    allowNull: false
  },
  error_summary: {
    type: DataTypes.JSONB,
    allowNull: true
  },
  notes: {
    type: DataTypes.TEXT,
    allowNull: true
  }
}, {
  tableName: 'upload_batches',
  timestamps: true,
  underscored: true
});

export default UploadBatch;
