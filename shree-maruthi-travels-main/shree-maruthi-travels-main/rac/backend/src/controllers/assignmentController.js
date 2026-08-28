import Assignment from '../models/Assignment.js';
import Booking from '../models/Booking.js';
import Driver from '../models/Driver.js';
import MessageLog from '../models/MessageLog.js';
import { sendWhatsAppMessage } from '../services/whatsappService.js';

const generateWhatsAppMessage = (booking) => {
  const pickupTime = booking.pickup_time ? booking.pickup_time.substring(0, 5) + ' AM' : 'N/A';
  const endTime = booking.end_time ? booking.end_time.substring(0, 5) + ' PM' : 'N/A';
  const routeText = booking.route_text ? (booking.route_text.substring(0, 100) + (booking.route_text.length > 100 ? '...' : '')) : 'N/A';

  return `New Ride Assigned

Booking ID: ${booking.source_booking_id}
Date: ${new Date(booking.trip_date).toLocaleDateString('en-US', { day: '2-digit', month: 'short', year: '2-digit' }).replace(/\//g, '-')}
Employee: ${booking.employee_name}
Pickup: ${booking.planned_start || 'N/A'}
Route: ${routeText}
Pickup Time: ${pickupTime}
End Time: ${endTime}
Duty Type: ${booking.duty_type || 'N/A'}
Cab Type: ${booking.cab_type || 'N/A'}
Amount: ₹${booking.amount}

Please confirm this trip.`;
};

export const createAssignment = async (req, res) => {
  try {
    const { booking_id, driver_id, assignment_notes, send_message_now = true } = req.body;

    // Validation
    if (!booking_id || !driver_id) {
      return res.status(400).json({ success: false, message: 'Booking ID and Driver ID required' });
    }

    // Check if booking exists
    const booking = await Booking.findByPk(booking_id);
    if (!booking) {
      return res.status(404).json({ success: false, message: 'Booking not found' });
    }

    // Check if already assigned
    if (booking.assigned_driver_id) {
      return res.status(409).json({ success: false, message: 'Booking is already assigned' });
    }

    // Check if driver exists
    const driver = await Driver.findByPk(driver_id);
    if (!driver) {
      return res.status(404).json({ success: false, message: 'Driver not found' });
    }

    // Create assignment
    const assignment = await Assignment.create({
      booking_id,
      driver_id,
      assigned_by: req.user.user_id,
      assignment_notes: assignment_notes ? assignment_notes.substring(0, 500) : null,
      whatsapp_message_status: send_message_now ? 'pending' : 'pending'
    });

    // Update booking status
    await booking.update({
      status: 'Assigned',
      assigned_driver_id: driver_id,
      assigned_at: new Date()
    });

    // Generate WhatsApp message
    if (send_message_now && driver.whatsapp_number) {
      const messageBody = generateWhatsAppMessage(booking);
      
      // Create message log entry
      const messageLog = await MessageLog.create({
        booking_id,
        driver_id,
        assignment_id: assignment.assignment_id,
        phone_number: driver.whatsapp_number,
        message_body: messageBody,
        provider_name: process.env.WHATSAPP_PROVIDER || 'twilio',
        send_status: 'queued'
      });

      // Send WhatsApp message via configured provider
      try {
        const sendResult = await sendWhatsAppMessage(
          driver.whatsapp_number,
          messageBody,
          messageLog.message_id
        );

        if (sendResult.success) {
          // Update message status
          await messageLog.update({
            send_status: 'sent',
            provider_message_id: sendResult.providerId || sendResult.messageId || null,
            sent_at: new Date()
          });

          await assignment.update({ whatsapp_message_status: 'sent' });

          console.log(`[ASSIGNMENT] WhatsApp sent to ${driver.whatsapp_number}`);
        } else {
          // Message failed to send
          await messageLog.update({
            send_status: 'failed',
            error_message: sendResult.error,
            sent_at: new Date()
          });

          await assignment.update({ whatsapp_message_status: 'failed' });

          console.error(`[ASSIGNMENT] WhatsApp send failed: ${sendResult.error}`);
        }
      } catch (err) {
        console.error('[ASSIGNMENT] Error sending WhatsApp:', err.message);
        await messageLog.update({
          send_status: 'failed',
          error_message: err.message,
          sent_at: new Date()
        });
      }
    }

    res.status(201).json({
      success: true,
      message: 'Booking assigned successfully',
      assignment_id: assignment.assignment_id,
      whatsapp_status: send_message_now ? 'queued' : 'pending'
    });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const getAssignment = async (req, res) => {
  try {
    const { assignment_id } = req.params;
    const assignment = await Assignment.findByPk(assignment_id, {
      include: [
        { model: Booking, attributes: ['source_booking_id', 'employee_name'] },
        { model: Driver, attributes: ['driver_name', 'whatsapp_number'] }
      ]
    });

    if (!assignment) {
      return res.status(404).json({ success: false, message: 'Assignment not found' });
    }

    res.json({ success: true, data: assignment });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const resendMessage = async (req, res) => {
  try {
    const { assignment_id } = req.params;
    const assignment = await Assignment.findByPk(assignment_id, {
      include: [Booking, Driver]
    });

    if (!assignment) {
      return res.status(404).json({ success: false, message: 'Assignment not found' });
    }

    const messageBody = generateWhatsAppMessage(assignment.booking);

    // Create or update message log
    let messageLog = await MessageLog.findOne({
      where: { assignment_id }
    });

    if (messageLog) {
      messageLog.retry_count += 1;
      messageLog.send_status = 'queued';
      await messageLog.save();
    } else {
      messageLog = await MessageLog.create({
        booking_id: assignment.booking_id,
        driver_id: assignment.driver_id,
        assignment_id,
        phone_number: assignment.driver.whatsapp_number,
        message_body: messageBody,
        provider_name: process.env.WHATSAPP_PROVIDER || 'twilio',
        send_status: 'queued',
        retry_count: 1
      });
    }

    // TODO: Queue WhatsApp message sending
    await assignment.update({ whatsapp_message_status: 'queued' });

    res.json({
      success: true,
      message: 'Message queued for resend',
      whatsapp_message_status: 'queued'
    });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};
