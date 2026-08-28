import Booking from '../models/Booking.js';
import UploadBatch from '../models/UploadBatch.js';
import Driver from '../models/Driver.js';
import { Op } from 'sequelize';

export const getBookings = async (req, res) => {
  try {
    const { page = 1, limit = 50, date, status, search, assigned_driver_id, sort_by = 'created_at', sort_order = 'DESC' } = req.query;
    const offset = (page - 1) * limit;

    let where = {};

    if (date) {
      where.trip_date = date;
    }

    if (status) {
      where.status = status;
    }

    if (search) {
      where[Op.or] = [
        { source_booking_id: { [Op.iLike]: `%${search}%` } },
        { employee_name: { [Op.iLike]: `%${search}%` } },
        { source_name: { [Op.iLike]: `%${search}%` } }
      ];
    }

    if (assigned_driver_id) {
      where.assigned_driver_id = assigned_driver_id;
    }

    // Calculate status counts for the current context (date and search, but NOT status filter)
    const statsWhere = { ...where };
    delete statsWhere.status;

    const [total, unassigned, assigned, completed, cancelled] = await Promise.all([
      Booking.count({ where: statsWhere }),
      Booking.count({ where: { ...statsWhere, status: 'Unassigned' } }),
      Booking.count({ where: { ...statsWhere, status: 'Assigned' } }),
      Booking.count({ where: { ...statsWhere, status: 'Completed' } }),
      Booking.count({ where: { ...statsWhere, status: 'Cancelled' } })
    ]);

    const { count, rows } = await Booking.findAndCountAll({
      where,
      limit: parseInt(limit),
      offset,
      order: [[sort_by, sort_order]],
      attributes: [
        'booking_id', 'source_booking_id', 'trip_date', 'employee_name',
        'source_name', 'planned_start', 'route_text', 'pickup_time',
        'end_time', 'duty_type', 'cab_type', 'amount', 'status',
        'assigned_driver_id', 'assigned_at'
      ]
    });

    res.json({
      success: true,
      data: rows,
      summary: {
        total,
        unassigned,
        assigned,
        completed,
        cancelled
      },
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

export const getBooking = async (req, res) => {
  try {
    const { booking_id } = req.params;
    const booking = await Booking.findByPk(booking_id);

    if (!booking) {
      return res.status(404).json({ success: false, message: 'Booking not found' });
    }

    // If booking has an assigned driver, fetch driver details
    let assignedDriver = null;
    if (booking.assigned_driver_id) {
      assignedDriver = await Driver.findByPk(booking.assigned_driver_id);
    }

    const response = {
      ...booking.toJSON(),
      assignedDriver: assignedDriver
    };

    res.json({ success: true, data: response });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const updateBookingStatus = async (req, res) => {
  try {
    const { booking_id } = req.params;
    const { status } = req.body;

    const booking = await Booking.findByPk(booking_id);
    if (!booking) {
      return res.status(404).json({ success: false, message: 'Booking not found' });
    }

    await booking.update({ status });

    res.json({ success: true, message: 'Booking status updated' });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};
