import MessageLog from '../models/MessageLog.js';
import Booking from '../models/Booking.js';
import Driver from '../models/Driver.js';
import { Op } from 'sequelize';

export const getMessages = async (req, res) => {
  try {
    const { page = 1, limit = 50, send_status, delivery_status, date_from, date_to } = req.query;
    const offset = (page - 1) * limit;

    let where = {};

    if (send_status) {
      where.send_status = send_status;
    }

    if (delivery_status) {
      where.delivery_status = delivery_status;
    }

    if (date_from || date_to) {
      where.sent_at = {};
      if (date_from) {
        where.sent_at[Op.gte] = new Date(date_from);
      }
      if (date_to) {
        const toDate = new Date(date_to);
        toDate.setHours(23, 59, 59, 999);
        where.sent_at[Op.lte] = toDate;
      }
    }

    const { count, rows } = await MessageLog.findAndCountAll({
      where,
      include: [
        { model: Booking, attributes: ['source_booking_id'] },
        { model: Driver, attributes: ['driver_name'] }
      ],
      limit: parseInt(limit),
      offset,
      order: [['sent_at', 'DESC']]
    });

    res.json({
      success: true,
      data: rows,
      pagination: {
        page: parseInt(page),
        limit: parseInt(limit),
        total: count
      }
    });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const getMessage = async (req, res) => {
  try {
    const { message_id } = req.params;
    const message = await MessageLog.findByPk(message_id, {
      include: [
        { model: Booking, attributes: ['source_booking_id', 'employee_name'] },
        { model: Driver, attributes: ['driver_name'] }
      ]
    });

    if (!message) {
      return res.status(404).json({ success: false, message: 'Message not found' });
    }

    res.json({ success: true, data: message });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};
