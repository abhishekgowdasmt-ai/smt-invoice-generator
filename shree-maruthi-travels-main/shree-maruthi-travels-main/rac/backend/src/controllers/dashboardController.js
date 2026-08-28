import Booking from '../models/Booking.js';
import UploadBatch from '../models/UploadBatch.js';
import MessageLog from '../models/MessageLog.js';
import { Op } from 'sequelize';

export const getDashboardSummary = async (req, res) => {
  try {
    const today = new Date();
    today.setHours(0, 0, 0, 0);

    const totalUploadedToday = await UploadBatch.count({
      where: {
        createdAt: { [Op.gte]: today }
      }
    });

    const unassignedRides = await Booking.count({
      where: { status: 'Unassigned' }
    });

    const assignedRides = await Booking.count({
      where: { status: 'Assigned' }
    });

    const messageSentCount = await MessageLog.count({
      where: { send_status: 'sent' }
    });

    const messageFailedCount = await MessageLog.count({
      where: { send_status: 'failed' }
    });

    const completedRides = await Booking.count({
      where: { status: 'Completed' }
    });

    const cancelledRides = await Booking.count({
      where: { status: 'Cancelled' }
    });

    res.json({
      success: true,
      data: {
        total_uploaded_today: totalUploadedToday,
        unassigned_rides: unassignedRides,
        assigned_rides: assignedRides,
        completed_rides: completedRides,
        cancelled_rides: cancelledRides,
        message_sent_count: messageSentCount,
        message_failed_count: messageFailedCount,
        upload_timestamp: new Date().toISOString()
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};
