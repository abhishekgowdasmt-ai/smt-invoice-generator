import sequelize from '../src/config/database.js';
import User from '../src/models/User.js';
import Driver from '../src/models/Driver.js';
import { hashPassword } from '../src/utils/auth.js';

const seed = async () => {
  try {
    console.log('🌱 Seeding database...');
    
    // Sync database
    await sequelize.sync({ alter: true });
    console.log('✅ Database synchronized');

    // Create test admin user
    const existingUser = await User.findOne({ where: { email: 'admin@dispatch.local' } });
    if (!existingUser) {
      const hashedPassword = await hashPassword('Admin@12345');
      await User.create({
        email: 'admin@dispatch.local',
        password_hash: hashedPassword,
        first_name: 'Admin',
        last_name: 'User',
        role: 'admin',
        active: true
      });
      console.log('✅ Admin user created: admin@dispatch.local / Admin@12345');
    } else {
      console.log('ℹ️ Admin user already exists');
    }

    // Create sample drivers
    const sampleDrivers = [
      { driver_name: 'RAJA KUMAR', whatsapp_number: '+919876543210', vehicle_number: 'KA-01-AB-1234', vehicle_type: 'SEDAN', home_area: 'BANGALORE' },
      { driver_name: 'SHARMA JI', whatsapp_number: '+919876543211', vehicle_number: 'KA-01-CD-3456', vehicle_type: 'SEDAN', home_area: 'BANGALORE' },
      { driver_name: 'GUPTA', whatsapp_number: '+919876543212', vehicle_number: 'KA-01-EF-5678', vehicle_type: 'SUV', home_area: 'WHITEFIELD' }
    ];

    for (const driverData of sampleDrivers) {
      const existingDriver = await Driver.findOne({ where: { whatsapp_number: driverData.whatsapp_number } });
      if (!existingDriver) {
        await Driver.create(driverData);
        console.log(`✅ Driver created: ${driverData.driver_name}`);
      }
    }

    console.log('✅ Database seeding completed!');
    process.exit(0);
  } catch (err) {
    console.error('❌ Seeding failed:', err.message);
    process.exit(1);
  }
};

seed();
