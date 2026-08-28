const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

// Generate a simple JWT token for admin user
const jwt = require('jsonwebtoken');
const token = jwt.sign(
  { 
    user_id: '5e97fca0-0000-0000-aaa0-000000000001',
    email: 'admin@dispatch.local'
  },
  'your_secret_key',
  { algorithm: 'HS256' }
);

console.log('Generated token:', token);

// Read the file
const filePath = './backend/uploads/1773153426718_Sample data.xlsx';
const fileStream = fs.createReadStream(filePath);

// Create form data
const form = new FormData();
form.append('file', fileStream);

// Make the request
axios.post('http://localhost:3000/api/v1/uploads/excel', form, {
  headers: {
    ...form.getHeaders(),
    'Authorization': `Bearer ${token}`
  }
})
.then(res => {
  console.log('Success:', res.data);
  process.exit(0);
})
.catch(err => {
  console.log('Error:', err.response?.data || err.message);
  process.exit(1);
});
