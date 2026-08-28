import UploadBatch from '../models/UploadBatch.js';
import Booking from '../models/Booking.js';
import multer from 'multer';
import path from 'path';
import fs from 'fs';
import XLSX from 'xlsx';
import { fileURLToPath } from 'url';
import { Op } from 'sequelize';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Configure multer for file uploads
const uploadsDir = path.join(__dirname, '../../uploads');
if (!fs.existsSync(uploadsDir)) {
  fs.mkdirSync(uploadsDir, { recursive: true });
}

const storage = multer.diskStorage({
  destination: uploadsDir,
  filename: (req, file, cb) => {
    const uniqueName = `${Date.now()}_${file.originalname}`;
    cb(null, uniqueName);
  }
});

const upload = multer({
  storage,
  fileFilter: (req, file, cb) => {
    if (!['.xlsx', '.xls'].includes(path.extname(file.originalname).toLowerCase())) {
      cb(new Error('Only Excel files are allowed'));
    } else if (file.size > parseInt(process.env.MAX_FILE_SIZE || 10485760)) {
      cb(new Error('File size exceeds maximum limit'));
    } else {
      cb(null, true);
    }
  }
});

const COLUMN_MAPPING = {
  'SL NO': 'sl_no',
  'BOOKING ID': 'source_booking_id',
  'DATE': 'trip_date',
  'NAME': 'source_name',
  'CAB REG NO': 'source_vehicle_no',
  'MOBIL NO': 'source_mobile',
  'PLAND START': 'planned_start',
  'END LOACTION': 'route_text',
  'PICKUP TIME': 'pickup_time',
  'END TIME': 'end_time',
  'TOTAL HRS SMT': 'total_hours_text',
  'CAB TYPE': 'cab_type',
  'EMP NAME': 'employee_name',
  'START KM': 'start_km',
  'END KM': 'end_km',
  'SMT TOTAL KM': 'total_km',
  'DUTY TYPE': 'duty_type',
  'DRIVER HRS': 'driver_hours',
  'DRIVER KM': 'driver_km',
  'TOLL': 'toll',
  'PARKING': 'parking',
  'AMOUNT': 'amount',
  'REMARKS': 'remarks'
};

const parseExcelDate = (excelDate) => {
  try {
    if (!excelDate) return null;
    
    if (typeof excelDate === 'string') {
      // Try parsing DD/MM/YYYY format first (18/12/2025)
      if (excelDate.includes('/')) {
        const parts = excelDate.split('/');
        if (parts.length === 3) {
          const day = parseInt(parts[0], 10);
          const month = parseInt(parts[1], 10);
          const year = parseInt(parts[2], 10);
          
          // Handle 2-digit years (25 -> 2025)
          const fullYear = year < 100 ? (year > 50 ? 1900 + year : 2000 + year) : year;
          
          if (day >= 1 && day <= 31 && month >= 1 && month <= 12) {
            const date = new Date(fullYear, month - 1, day);
            if (!isNaN(date.getTime())) {
              return date;
            }
          }
        }
      }
      
      // Try parsing other string dates like "6-Mar-26"
      const parsed = new Date(excelDate);
      if (!isNaN(parsed.getTime())) {
        return parsed;
      }
      
      console.warn('[PARSE] Invalid date string:', excelDate);
      return null;
    }
    
    // Excel stores dates as numbers
    if (typeof excelDate !== 'number') {
      console.warn('[PARSE] Invalid date type:', typeof excelDate);
      return null;
    }
    
    const date = new Date((excelDate - 25569) * 86400 * 1000);
    if (isNaN(date.getTime())) {
      console.warn('[PARSE] Invalid calculated date from value:', excelDate);
      return null;
    }
    return date;
  } catch (err) {
    console.warn('[PARSE] Date parsing error:', err.message);
    return null;
  }
};

const parseTime = (timeStr) => {
  if (!timeStr) return null;
  const str = String(timeStr).trim();
  const timeRegex = /(\d{1,2})[\.:]{1}(\d{2})/;
  const match = str.match(timeRegex);
  if (match) {
    const [, hours, minutes] = match;
    return `${String(hours).padStart(2, '0')}:${minutes}`;
  }
  return null;
};

const parseNumeric = (value, defaultValue = null) => {
  if (!value) return defaultValue;
  
  // If it's already a number, return it
  if (typeof value === 'number') {
    return isNaN(value) ? defaultValue : value;
  }
  
  // Convert to string and extract all numbers
  const str = String(value).trim();
  if (!str) return defaultValue;
  
  // Extract all digits from the string
  const matches = str.match(/\d+/g);
  if (!matches || matches.length === 0) return defaultValue;
  
  // If multiple numbers, take the last one (e.g., "12HRS120KM" -> "120", "19HRS" -> "19")
  // For cases like "12HRS120KM", the significant number is usually last
  let result = parseInt(matches[matches.length - 1], 10);
  
  // Special case: for values like "19HRS" we want the first number, not last
  // If we have single digit followed by text, use that
  if (matches.length === 1) {
    result = parseInt(matches[0], 10);
  }
  
  return isNaN(result) ? defaultValue : result;
};

// Truncate string fields to match database column limits
const truncateFields = (row) => {
  const fieldLimits = {
    source_booking_id: 50,
    source_mobile: 20,
    source_vehicle_no: 50,
    planned_start: 100,
    total_hours_text: 50,
    cab_type: 50,
    duty_type: 100,
    vendor_name: 200,
    source_name: 200,
    employee_name: 200
  };

  Object.keys(fieldLimits).forEach((field) => {
    if (row[field] && typeof row[field] === 'string') {
      const maxLen = fieldLimits[field];
      if (row[field].length > maxLen) {
        console.log(`[TRUNCATE] Field "${field}": length ${row[field].length} -> ${maxLen}`);
        row[field] = row[field].substring(0, maxLen);
      }
    }
  });

  return row;
};

const validateRow = (row, rowIndex) => {
  const errors = [];

  if (!row.source_booking_id) {
    errors.push('Booking ID is empty');
  }

  if (!row.employee_name) {
    errors.push('Employee name is empty');
  }

  // Trip date is mandatory
  if (!row.trip_date) {
    errors.push('Trip date is invalid or missing');
  }

  // Amount can be empty or zero - set to default if missing
  if (!row.amount || isNaN(row.amount)) {
    row.amount = 0; // Default amount if missing
  } else {
    row.amount = parseFloat(row.amount);
  }

  // Note: trip_date is already parsed and validated above
  // If it's invalid, it will be null

  return errors;
};

export const uploadExcel = async (req, res) => {
  try {
    console.log('[UPLOAD CONTROLLER] Starting upload process');
    console.log('[UPLOAD CONTROLLER] req.user:', req.user ? 'exists' : 'MISSING');
    console.log('[UPLOAD CONTROLLER] req.file:', req.file ? req.file.originalname : 'MISSING');
    
    if (!req.file) {
      console.log('[UPLOAD CONTROLLER] No file found');
      return res.status(400).json({ success: false, message: 'No file uploaded' });
    }

    // Read Excel file
    console.log('[UPLOAD CONTROLLER] Reading Excel file:', req.file.path);
    const workbook = XLSX.readFile(req.file.path);
    const sheetName = workbook.SheetNames[0];
    const worksheet = workbook.Sheets[sheetName];
    const rawData = XLSX.utils.sheet_to_json(worksheet);

    console.log('[UPLOAD CONTROLLER] Excel parsed. Rows:', rawData.length);

    if (rawData.length === 0) {
      return res.status(400).json({ success: false, message: 'Excel file is empty' });
    }

    // Create batch record
    console.log('[UPLOAD CONTROLLER] Creating batch record');
    const batch = await UploadBatch.create({
      file_name: req.file.originalname,
      file_path: req.file.path,
      file_size: req.file.size,
      uploaded_by: req.user.user_id,
      total_rows: rawData.length,
      import_status: 'pending'
    });
    console.log('[UPLOAD CONTROLLER] Batch created:', batch.batch_id);

    // Process rows
    let successRows = 0;
    let failedRows = 0;
    const errors = [];
    const processedRows = [];

    for (let i = 0; i < rawData.length; i++) {
      const rawRow = rawData[i];
      const rowIndex = i + 2; // +2 because Excel is 1-indexed and has header

      // Map Excel columns to system fields
      const row = {};
      Object.entries(COLUMN_MAPPING).forEach(([excelCol, systemField]) => {
        if (rawRow[excelCol] !== undefined) {
          row[systemField] = rawRow[excelCol];
        }
      });

      // Special parsing for certain fields
      if (row.trip_date) {
        const parsedDate = parseExcelDate(row.trip_date);
        if (parsedDate && !isNaN(parsedDate.getTime())) {
          row.trip_date = parsedDate.toISOString().split('T')[0];
        } else {
          row.trip_date = null;
        }
      }
      if (row.pickup_time) {
        row.pickup_time = parseTime(row.pickup_time);
      }
      if (row.end_time) {
        row.end_time = parseTime(row.end_time);
      }
      
      // Parse numeric fields that may have text mixed in
      row.start_km = parseNumeric(row.start_km, 0);
      row.end_km = parseNumeric(row.end_km, 0);
      row.total_km = parseNumeric(row.total_km, 0);
      row.driver_hours = parseNumeric(row.driver_hours, 0);
      row.driver_km = parseNumeric(row.driver_km, 0);
      row.toll = parseNumeric(row.toll, 0);
      row.parking = parseNumeric(row.parking, 0);
      row.amount = parseNumeric(row.amount, 0);

      // Truncate string fields to match database column limits
      truncateFields(row);

      // Validate
      const rowErrors = validateRow(row, rowIndex);
      if (rowErrors.length > 0) {
        failedRows++;
        errors.push({
          row_number: rowIndex,
          booking_id: row.source_booking_id,
          error: rowErrors.join('; ')
        });
        continue;
      }

      // Create booking
      processedRows.push({
        ...row,
        upload_batch_id: batch.batch_id,
        status: 'Unassigned'
      });
      successRows++;
    }

    console.log('[UPLOAD CONTROLLER] Rows processed. Success:', successRows, 'Failed:', failedRows);

    // Bulk create bookings
    if (processedRows.length > 0) {
      console.log('[UPLOAD CONTROLLER] Creating bookings');
      await Booking.bulkCreate(processedRows, { ignoreDuplicates: true });
      console.log('[UPLOAD CONTROLLER] Bookings created');
    }

    // Update batch with results
    console.log('[UPLOAD CONTROLLER] Updating batch with results');
    await batch.update({
      success_rows: successRows,
      failed_rows: failedRows,
      import_status: failedRows === rawData.length ? 'failed' : 'completed',
      error_summary: errors
    });

    console.log('[UPLOAD CONTROLLER] Upload complete');
    res.status(201).json({
      success: true,
      batch_id: batch.batch_id,
      message: `File processed: ${successRows} rows imported, ${failedRows} rows failed`,
      status: 'completed',
      total_rows: rawData.length,
      success_rows: successRows,
      failed_rows: failedRows,
      errors: errors
    });
  } catch (err) {
    console.error('[UPLOAD CONTROLLER] FATAL ERROR:', err);
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const getUploadStatus = async (req, res) => {
  try {
    const { batch_id } = req.params;
    const batch = await UploadBatch.findByPk(batch_id);

    if (!batch) {
      return res.status(404).json({ success: false, message: 'Batch not found' });
    }

    res.json({
      success: true,
      batch_id: batch.batch_id,
      file_name: batch.file_name,
      import_status: batch.import_status,
      total_rows: batch.total_rows,
      success_rows: batch.success_rows,
      failed_rows: batch.failed_rows,
      error_summary: batch.error_summary,
      processed_at: batch.updated_at
    });
  } catch (err) {
    res.status(500).json({ success: false, message: 'Server error', error: err.message });
  }
};

export const getUploadHistory = async (req, res) => {
  try {
    const { page = 1, limit = 20, status } = req.query;
    const offset = (page - 1) * limit;

    let where = {};
    if (status) {
      where.import_status = status;
    }

    const { count, rows } = await UploadBatch.findAndCountAll({
      where,
      limit: parseInt(limit),
      offset,
      order: [['uploaded_at', 'DESC']],
      attributes: ['batch_id', 'file_name', 'uploaded_by', 'uploaded_at', 'total_rows', 'success_rows', 'failed_rows', 'import_status']
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

export { upload };
