import sequelize from '../config/database.js';
import User from './User.js';
import Driver from './Driver.js';
import Booking from './Booking.js';
import Assignment from './Assignment.js';
import MessageLog from './MessageLog.js';
import UploadBatch from './UploadBatch.js';

export {
  sequelize,
  User,
  Driver,
  Booking,
  Assignment,
  MessageLog,
  UploadBatch
};
