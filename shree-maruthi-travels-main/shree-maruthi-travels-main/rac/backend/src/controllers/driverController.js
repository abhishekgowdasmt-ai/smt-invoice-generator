import Driver from '../models/Driver.js';
import Booking from '../models/Booking.js';
import MessageLog from '../models/MessageLog.js';
import Assignment from '../models/Assignment.js';
import { Op } from 'sequelize';

export const createDriver = async (req, res) => {
  try {
    const { driver_name, whatsapp_number, alternate_number, vehicle_number, vehicle_type, home_area, notes } = req.body;

    if (!driver_name || !whatsapp_number) {
      return res.status(400).json({ success: false, message: 'Driver name and WhatsApp number required' });
    }

    // Check if WhatsApp number already exists
    const existingDriver = await Driver.findOne({ where: { whatsapp_number } });
    if (existingDriver) {
      return res.status(409).json({ success: false, message: 'WhatsApp number already exists' });
    }

    const driver = await Driver.create({
      driver_name,
      whatsapp_number,
      alternate_number,
      vehicle_number,
      vehicle_type,
      home_area,
      notes
    });

    res.status(201).json({ success: true, message: 'Driver created successfully', driver_id: driver.driver_id });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const getDrivers = async (req, res) => {
  try {
    const { page = 1, limit = 50, active_only = true, search } = req.query;
    const offset = (page - 1) * limit;

    let where = {};
    if (active_only === 'true') {
      where.active_status = true;
    }

    if (search) {
      where[Op.or] = [
        { driver_name: { [Op.iLike]: `%${search}%` } },
        { vehicle_number: { [Op.iLike]: `%${search}%` } },
        { whatsapp_number: { [Op.iLike]: `%${search}%` } }
      ];
    }

    const { count, rows } = await Driver.findAndCountAll({
      where,
      limit: parseInt(limit),
      offset,
      order: [['driver_name', 'ASC']]
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

export const getDriver = async (req, res) => {
  try {
    const { driver_id } = req.params;
    const driver = await Driver.findByPk(driver_id);

    if (!driver) {
      return res.status(404).json({ success: false, message: 'Driver not found' });
    }

    res.json({ success: true, data: driver });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const updateDriver = async (req, res) => {
  try {
    const { driver_id } = req.params;
    const { driver_name, whatsapp_number, alternate_number, vehicle_number, vehicle_type, home_area, notes } = req.body;

    const driver = await Driver.findByPk(driver_id);
    if (!driver) {
      return res.status(404).json({ success: false, message: 'Driver not found' });
    }

    // Check if WhatsApp number is unique (if changed)
    if (whatsapp_number && whatsapp_number !== driver.whatsapp_number) {
      const existingDriver = await Driver.findOne({ where: { whatsapp_number } });
      if (existingDriver) {
        return res.status(409).json({ success: false, message: 'WhatsApp number already exists' });
      }
    }

    await driver.update({
      driver_name: driver_name || driver.driver_name,
      whatsapp_number: whatsapp_number || driver.whatsapp_number,
      alternate_number: alternate_number !== undefined ? alternate_number : driver.alternate_number,
      vehicle_number: vehicle_number !== undefined ? vehicle_number : driver.vehicle_number,
      vehicle_type: vehicle_type !== undefined ? vehicle_type : driver.vehicle_type,
      home_area: home_area !== undefined ? home_area : driver.home_area,
      notes: notes !== undefined ? notes : driver.notes
    });

    res.json({ success: true, message: 'Driver updated successfully' });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const updateDriverStatus = async (req, res) => {
  try {
    const { driver_id } = req.params;
    const { active_status } = req.body;

    const driver = await Driver.findByPk(driver_id);
    if (!driver) {
      return res.status(404).json({ success: false, message: 'Driver not found' });
    }

    await driver.update({ active_status });

    res.json({ success: true, message: 'Driver status updated' });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};
